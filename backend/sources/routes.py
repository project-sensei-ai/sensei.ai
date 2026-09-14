import os
from datetime import datetime, timezone
from typing import Annotated, Literal, Union
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field, field_validator

from auth.deps import get_current_user
from core import secrets
from core.config import settings
from db.chroma import get_chroma, get_workspace_collection
from db.database import get_db
from db.membership import require_owner, require_workspace
from db.models import serialize_source

router = APIRouter(tags=["sources"])

ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt", ".docx"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


# ── Pydantic input models (discriminated by type) ─────────────────────────────

class GithubSourceIn(BaseModel):
    type: Literal["github"]
    pat: str = Field(..., min_length=1)
    repo: str = Field(..., pattern=r"^[\w.-]+/[\w.-]+$")
    label: str = ""


class UrlSourceIn(BaseModel):
    type: Literal["url"]
    urls: list[str] = Field(..., min_length=1, max_length=20)
    label: str = "URLs"


class ConfluenceSourceIn(BaseModel):
    type: Literal["confluence"]
    base_url: str
    email: str
    api_token: str
    space_key: str
    label: str = ""

    @field_validator("base_url")
    @classmethod
    def _looks_like_a_site(cls, v: str) -> str:
        """
        Accept whatever is in the address bar. People paste the page they are
        looking at, not the site root, so trim a full page URL down to the site:
            https://x.atlassian.net/wiki/spaces/ENG/pages/393218/Some+Doc
                 -> https://x.atlassian.net/wiki
        Redirect URLs carry query strings (`?continue=...`) — drop those too.
        """
        v = v.strip().split("#")[0].split("?")[0].rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError(
                "Confluence site must be a URL, like https://your-org.atlassian.net/wiki "
                "— copy it from the address bar of your Confluence tab"
            )
        marker = "/wiki"
        idx = v.find(marker + "/")
        if idx != -1:
            v = v[: idx + len(marker)]
        return v


class JiraSourceIn(BaseModel):
    type: Literal["jira"]
    base_url: str
    email: str
    api_token: str
    project_key: str
    label: str = ""

    @field_validator("base_url")
    @classmethod
    def _looks_like_a_site(cls, v: str) -> str:
        v = v.strip().split("#")[0].split("?")[0].rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError(
                "Jira site must be a URL, like https://your-org.atlassian.net"
            )
        # People paste the ticket they are looking at; cut it back to the site.
        marker = "/browse/"
        idx = v.find(marker)
        if idx != -1:
            v = v[:idx]
        return v


class SlackSourceIn(BaseModel):
    type: Literal["slack"]
    token: str = Field(..., min_length=1)
    channel: str = Field(..., min_length=1)
    label: str = ""

    @field_validator("channel")
    @classmethod
    def _clean_channel(cls, v: str) -> str:
        v = v.strip().lower().lstrip("#").strip()
        if not v:
            raise ValueError("Enter a channel name, like general")
        return v


# The update flavours reuse every validator but let a blank secret mean "keep
# the stored one" — the UI never sees the secret, so re-typing it on every
# edit would be the only way to change the channel otherwise.
class JiraSourceUpdate(JiraSourceIn):
    api_token: str = ""


class SlackSourceUpdate(SlackSourceIn):
    token: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _verify_confluence(body) -> None:
    """
    Confirm the site answers, the credentials work, and the space exists —
    before anything is stored. Each failure gets a message that says what to do,
    and a wrong space key lists the keys that actually exist.
    """
    import base64 as _b64
    import httpx as _httpx

    base = body.base_url.rstrip("/")
    space_key = body.space_key.strip().upper()
    auth = _b64.b64encode(f"{body.email}:{body.api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}

    # Runs before _source_doc, so the token here is still the one the owner
    # typed. Nothing encrypted reaches this function.
    async with _httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as c:
        try:
            r = await c.get(f"{base}/rest/api/space", params={"limit": 100})
        except Exception as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Couldn't reach {base} — check the site address. ({exc.__class__.__name__})",
            )

        if r.status_code in (401, 403):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Confluence rejected those credentials. The email must be the Atlassian "
                "account that created the API token, and the token must not have expired.",
            )
        if r.status_code == 404 or "application/json" not in r.headers.get("content-type", ""):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"{base} doesn't look like a Confluence site. The address usually ends in "
                "/wiki, for example https://your-org.atlassian.net/wiki",
            )
        if r.status_code != 200:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Confluence returned {r.status_code} when listing spaces.",
            )

        spaces = r.json().get("results", [])
        keys = {sp.get("key", "") for sp in spaces}

        if space_key not in keys:
            # The listing is paginated and may omit personal spaces, so ask for
            # this exact key before deciding it does not exist.
            direct = await c.get(f"{base}/rest/api/space/{space_key}")
            if direct.status_code != 200:
                def describe(sp: dict) -> str:
                    key = sp.get("key", "")
                    name = sp.get("name", "")
                    kind = " (personal)" if key.startswith("~") else ""
                    return f"{key}{kind} — {name}" if name else f"{key}{kind}"

                visible = "; ".join(describe(sp) for sp in spaces if sp.get("key")) or "none"
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"No space with key '{space_key}' is visible to this account. "
                    f"Spaces it can see: {visible}",
                )


async def _verify_jira(body) -> None:
    """
    Confirm the site answers, the credentials work, and the project exists —
    before anything is stored. Same shape as the Confluence check; a wrong
    project key lists the keys that actually exist.
    """
    import base64 as _b64
    import httpx as _httpx

    base = body.base_url.rstrip("/")
    project_key = body.project_key.strip().upper()
    auth = _b64.b64encode(f"{body.email}:{body.api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}

    async with _httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as c:
        try:
            r = await c.get(f"{base}/rest/api/3/myself")
        except Exception as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Couldn't reach {base} — check the site address. ({exc.__class__.__name__})",
            )

        if r.status_code in (401, 403):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Jira rejected those credentials. The email must be the Atlassian "
                "account that created the API token, and the token must not have expired.",
            )
        if r.status_code == 404 or "application/json" not in r.headers.get("content-type", ""):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"{base} doesn't look like a Jira site. The address is usually "
                "https://your-org.atlassian.net",
            )
        if r.status_code != 200:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Jira returned {r.status_code} when checking the account.",
            )

        project = await c.get(f"{base}/rest/api/3/project/{project_key}")
        if project.status_code != 200:
            listing = await c.get(
                f"{base}/rest/api/3/project/search", params={"maxResults": 100}
            )
            visible = "; ".join(
                p.get("key", "") for p in listing.json().get("values", []) if p.get("key")
            ) or "none"
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"No project with key '{project_key}' is visible to this account. "
                f"Projects it can see: {visible}",
            )


async def _verify_slack(body) -> dict:
    """
    Confirm the bot token works, the team answers, and the bot can see the
    channel — before anything is stored. Returns what the source needs to read:
    the team domain (for permalinks), the channel id, and its canonical name.
    """
    import httpx as _httpx

    headers = {"Authorization": f"Bearer {body.token}", "Content-Type": "application/json"}

    async with _httpx.AsyncClient(headers=headers, timeout=15) as c:
        try:
            r = await c.get("https://slack.com/api/auth.test")
        except Exception as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Couldn't reach Slack. ({exc.__class__.__name__})",
            )

        auth = r.json()
        if not auth.get("ok"):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Slack rejected that token ({auth.get('error')}). The token is a "
                "bot token (xoxb-…) from api.slack.com/apps → your app → OAuth & "
                "Permissions — reinstall the app if it was rotated.",
            )

        team_domain = auth.get("url", "").replace("https://", "").rstrip("/").split(".")[0]
        if not team_domain:
            team_domain = auth.get("team", "slack")

        channel = await _slack_find_channel(c, body.channel)

        # Public channels the app is not in still show in the list; history
        # would fail on them, so say so before anything is stored.
        info = await c.get(
            "https://slack.com/api/conversations.info",
            params={"channel": channel["id"]},
        )
        info_payload = info.json()
        if info_payload.get("ok") and not (info_payload.get("channel") or {}).get("is_member"):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"The bot can see #{body.channel} but is not in it. Open the "
                "channel → Details → Add apps → add this app, then re-save.",
            )
        if not info_payload.get("ok") and info_payload.get("error") == "not_in_channel":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"The bot is not in #{body.channel}. Open the channel → Details → "
                "Add apps → add this app, then re-save.",
            )

        return {"team_domain": team_domain, "channel_id": channel["id"],
                "channel_name": channel.get("name", body.channel)}


async def _slack_find_channel(client, name: str) -> dict:
    """Resolve a channel name to its Slack object, listing what is visible on a miss."""
    cursor = None
    while True:
        params = {**({"cursor": cursor} if cursor else {}),
                  "types": "public_channel,private_channel",
                  "exclude_archived": True, "limit": 200}
        r = await client.get("https://slack.com/api/conversations.list", params=params)
        payload = r.json()
        if not payload.get("ok"):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Slack couldn't list channels: {payload.get('error')}",
            )
        for ch in payload.get("channels", []):
            if ch.get("name") == name:
                return ch
        cursor = (payload.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break

    # Collect the names we did find so the owner can see what is actually there.
    visible = set()
    cursor = None
    while True:
        params = {**({"cursor": cursor} if cursor else {}),
                  "types": "public_channel,private_channel",
                  "exclude_archived": True, "limit": 200}
        r = await client.get("https://slack.com/api/conversations.list", params=params)
        payload = r.json()
        if payload.get("ok"):
            visible.update(ch.get("name", "") for ch in payload.get("channels", []))
        cursor = (payload.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break

    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        f"No channel '#{name}' is visible to this bot. Channels it can see: "
        f"{', '.join(sorted(visible)) or 'none'}",
    )


def _source_doc(workspace_id: str, source_type: str, label: str, config: dict, config_secret: dict | None = None) -> dict:
    now = datetime.now(timezone.utc)
    doc = {
        "_id": uuid4().hex,
        "workspace_id": workspace_id,
        "type": source_type,
        "label": label,
        "config": config,
        "status": "pending",
        "stats": {},
        "created_at": now,
        "updated_at": now,
    }
    if config_secret:
        # Encrypted here rather than at each call site, so no future connector
        # can forget to do it.
        doc["config_secret"] = secrets.encrypt_dict(config_secret)
    return doc


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def add_source(
    # Discriminated on `type`, so a bad Confluence field reports the Confluence
    # error. Without the discriminator pydantic tries each variant in turn and
    # surfaces the first one's complaint ("Input should be 'github'"), which
    # tells the user nothing about what they actually got wrong.
    body: Annotated[
        Union[GithubSourceIn, UrlSourceIn, ConfluenceSourceIn, JiraSourceIn, SlackSourceIn],
        Field(discriminator="type"),
    ],
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    ws = await require_owner(user, db, "add or remove sources")

    if body.type == "github":
        label = body.label or body.repo
        config = {"repo": body.repo}
        config_secret = {"pat": body.pat}
        doc = _source_doc(ws["_id"], "github", label, config, config_secret)

    elif body.type == "url":
        # Verify each URL is reachable before storing
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=8, follow_redirects=True) as _client:
            for _url in body.urls:
                try:
                    _r = await _client.head(_url, headers={"User-Agent": "Sensei/1.0"})
                    if _r.status_code == 405:  # HEAD not allowed — fall back to GET
                        _r = await _client.get(_url, headers={"User-Agent": "Sensei/1.0"})
                    if _r.status_code == 404:
                        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"URL not found: {_url}")
                except HTTPException:
                    raise
                except Exception as _exc:
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"URL not reachable: {_url} — {_exc}")
        label = body.label or f"{len(body.urls)} URL(s)"
        config = {"urls": body.urls}
        doc = _source_doc(ws["_id"], "url", label, config)

    elif body.type == "confluence":
        # Check the credentials now rather than failing in a background task four
        # seconds later with an httpx message nobody can act on.
        await _verify_confluence(body)
        space_key = body.space_key.strip().upper()
        label = body.label or f"Confluence: {space_key}"
        config = {"base_url": body.base_url, "space_key": space_key, "email": body.email}
        config_secret = {"api_token": body.api_token}
        doc = _source_doc(ws["_id"], "confluence", label, config, config_secret)

    elif body.type == "jira":
        await _verify_jira(body)
        project_key = body.project_key.strip().upper()
        label = body.label or f"Jira: {project_key}"
        config = {"base_url": body.base_url, "project_key": project_key, "email": body.email}
        config_secret = {"api_token": body.api_token}
        doc = _source_doc(ws["_id"], "jira", label, config, config_secret)

    elif body.type == "slack":
        info = await _verify_slack(body)
        label = body.label or f"Slack: #{info['channel_name']}"
        config = {
            "channel_id": info["channel_id"],
            "channel_name": info["channel_name"],
            "team_domain": info["team_domain"],
        }
        config_secret = {"token": body.token}
        doc = _source_doc(ws["_id"], "slack", label, config, config_secret)

    await db.sources.insert_one(doc)
    return {"source": serialize_source(doc)}


@router.patch("/{source_id}")
async def update_source(
    source_id: str,
    body: Annotated[
        Union[JiraSourceUpdate, SlackSourceUpdate],
        Field(discriminator="type"),
    ],
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    ws = await require_owner(user, db, "add or remove sources")
    source = await db.sources.find_one({"_id": source_id, "workspace_id": ws["_id"]})
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    if source["type"] != body.type:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A source's type cannot be changed — delete it and add the new kind.",
        )

    stored = secrets.decrypt_dict(source.get("config_secret"))

    if body.type == "jira":
        token = body.api_token or stored.get("api_token", "")
        check = JiraSourceIn(
            type="jira", base_url=body.base_url, email=body.email,
            api_token=token, project_key=body.project_key,
        )
        await _verify_jira(check)
        project_key = check.project_key.strip().upper()
        label = body.label or source.get("label") or f"Jira: {project_key}"
        config = {"base_url": check.base_url, "project_key": project_key, "email": check.email}
        config_secret = {"api_token": token}
    else:
        token = body.token or stored.get("token", "")
        check = SlackSourceIn(type="slack", token=token, channel=body.channel)
        info = await _verify_slack(check)
        label = body.label or source.get("label") or f"Slack: #{info['channel_name']}"
        config = {
            "channel_id": info["channel_id"],
            "channel_name": info["channel_name"],
            "team_domain": info["team_domain"],
        }
        config_secret = {"token": token}

    # The indexed chunks belong to the old config — drop them so a re-ingest
    # starts clean, and reset to pending so the frontend polls for it.
    try:
        chroma = get_chroma(request)
        collection = get_workspace_collection(chroma, ws["_id"])
        if collection.count() > 0:
            collection.delete(where={"source_id": source_id})
    except Exception:
        pass  # ChromaDB cleanup is best-effort

    now = datetime.now(timezone.utc)
    await db.sources.update_one(
        {"_id": source_id},
        {"$set": {
            "config": config,
            "config_secret": secrets.encrypt_dict(config_secret),
            "label": label,
            "status": "pending",
            "stats": {},
            "error_message": None,
            "updated_at": now,
        }, "$unset": {"content_fingerprint": 1, "last_checked_at": 1}},
    )

    updated = await db.sources.find_one({"_id": source_id})
    return {"source": serialize_source(updated)}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    ws = await require_owner(user, db, "add or remove sources")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unsupported file type '{ext}'. Allowed: pdf, md, txt, docx")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 20 MB limit")

    source_id = uuid4().hex
    upload_dir = os.path.join(settings.CHROMA_PERSIST_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, f"{source_id}_{file.filename}")

    with open(save_path, "wb") as f:
        f.write(contents)

    label = file.filename or source_id
    s3_uri = None

    if settings.S3_UPLOAD_BUCKET:
        try:
            import boto3
            s3 = boto3.client("s3", region_name=settings.AWS_REGION)
            s3_key = f"uploads/{source_id}/{file.filename}"
            s3.put_object(
                Bucket=settings.S3_UPLOAD_BUCKET,
                Key=s3_key,
                Body=contents,
                ContentType=file.content_type or "application/octet-stream",
            )
            s3_uri = f"s3://{settings.S3_UPLOAD_BUCKET}/{s3_key}"

            if settings.BEDROCK_KB_ID and settings.BEDROCK_KB_DATA_SOURCE_ID:
                ba = boto3.client("bedrock-agent", region_name=settings.AWS_REGION)
                ba.start_ingestion_job(
                    knowledgeBaseId=settings.BEDROCK_KB_ID,
                    dataSourceId=settings.BEDROCK_KB_DATA_SOURCE_ID,
                )
        except Exception:
            pass  # S3/KB upload is best-effort; local ingest still runs

    config = {"filename": file.filename, "size": len(contents), "path": save_path, "s3_uri": s3_uri}
    now = datetime.now(timezone.utc)
    doc = {
        "_id": source_id,
        "workspace_id": ws["_id"],
        "type": "file",
        "label": label,
        "config": config,
        "status": "pending",
        "stats": {},
        "created_at": now,
        "updated_at": now,
    }
    await db.sources.insert_one(doc)
    return {"source": serialize_source(doc)}


@router.get("")
async def list_sources(
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    ws, _role = await require_workspace(user, db)
    cursor = db.sources.find({"workspace_id": ws["_id"]})
    sources = [serialize_source(doc) async for doc in cursor]
    return {"sources": sources}


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: str,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    ws = await require_owner(user, db, "add or remove sources")
    source = await db.sources.find_one({"_id": source_id, "workspace_id": ws["_id"]})
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")

    # Remove all chunks from ChromaDB for this source
    try:
        chroma = get_chroma(request)
        collection = get_workspace_collection(chroma, ws["_id"])
        if collection.count() > 0:
            collection.delete(where={"source_id": source_id})
    except Exception:
        pass  # ChromaDB cleanup is best-effort

    await db.sources.delete_one({"_id": source_id})
