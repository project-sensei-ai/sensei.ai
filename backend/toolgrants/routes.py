"""Tool grants — connect an MCP server, decide what the agent may do with it."""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from auth.deps import get_current_user
from core import secrets
from core.errors import humanise
from db.database import get_db
from db.membership import OWNER_ROLES, require_owner, require_workspace
from toolgrants import oauth, pool, registry

router = APIRouter(tags=["tools"])


class GrantIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    kind: Literal["mcp_http", "mcp_sse", "mcp_stdio"]
    url: str | None = None
    # e.g. "Bearer ghp_..." — stored encrypted, never returned.
    authorization: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    allow_write: bool = False

    @field_validator("url")
    @classmethod
    def _url(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("The server URL must start with http:// or https://")
        return v


class GrantPatch(BaseModel):
    allow_write: bool | None = None
    disabled_tools: list[str] | None = None
    name: str | None = Field(None, min_length=1, max_length=60)


def _check_shape(body: GrantIn) -> None:
    if body.kind in ("mcp_http", "mcp_sse") and not body.url:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A server URL is required")
    if body.kind == "mcp_stdio" and not body.command:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A command is required for a local server")


async def _probe_or_422(doc: dict, secret: dict) -> list[dict]:
    try:
        return await asyncio.wait_for(asyncio.to_thread(registry.probe, doc, secret), timeout=45)
    except asyncio.TimeoutError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The server did not answer within 45 seconds. Check the URL, and that it speaks MCP.",
        )
    except Exception as exc:
        text = str(exc)
        if "401" in text or "403" in text or "Unauthorized" in text:
            hint = "The server rejected the credential. Check the Authorization value."
        elif "404" in text:
            hint = "Nothing speaks MCP at that URL. Check the path — many servers use /mcp or /sse."
        else:
            hint = humanise(exc)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Could not connect: {hint}")


@router.post("", status_code=status.HTTP_201_CREATED)
async def connect_tool(body: GrantIn, user=Depends(get_current_user), db=Depends(get_db)):
    ws = await require_owner(user, db, "connect tools")
    _check_shape(body)

    secret: dict = {}
    if body.authorization:
        secret["authorization"] = body.authorization.strip()
    if body.env:
        secret["env"] = body.env

    now = datetime.now(timezone.utc)
    doc = {
        "_id": uuid4().hex,
        "workspace_id": ws["_id"],
        "name": body.name.strip(),
        "kind": body.kind,
        "url": body.url,
        "headers": body.headers,
        "command": body.command,
        "args": body.args,
        "allow_write": body.allow_write,
        "disabled_tools": [],
        "status": "connected",
        "created_at": now,
        "created_by": user["id"],
        "uses": 0,
    }
    # Connect now, so a broken grant never gets stored. The tool list it
    # returns is what the Trust page shows and what the write gate enforces.
    doc["tools"] = await _probe_or_422(doc, secret)
    if secret:
        doc["config_secret"] = secrets.encrypt_dict(
            {k: v for k, v in secret.items() if isinstance(v, str)}
        )
        if "env" in secret:
            doc["config_secret"]["env"] = {k: secrets.encrypt(v) for k, v in secret["env"].items()}

    await db.tool_grants.insert_one(doc)
    await pool.drop(ws["_id"])     # next turn opens a session that includes this
    return {"grant": registry.serialize_grant(doc, for_owner=True)}


class OAuthStartIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    url: str = Field(..., min_length=8)
    allow_write: bool = False


@router.get("/oauth/presets")
async def oauth_presets():
    return {"presets": oauth.OAUTH_PRESETS}


@router.post("/oauth/start", status_code=status.HTTP_202_ACCEPTED)
async def oauth_start(body: OAuthStartIn, request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    """
    Begin a login-based connection. Returns the vendor's login URL for the
    UI to open; the grant finishes in the background once the person is back.
    """
    ws = await require_owner(user, db, "connect tools")
    url = body.url.strip()
    if not url.startswith("https://"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "OAuth servers must be https://")
    now = datetime.now(timezone.utc)
    # A previous attempt at the same connection that never finished is noise,
    # not history. Replace it rather than stacking a second card.
    await db.tool_grants.delete_many({
        "workspace_id": ws["_id"], "kind": "mcp_oauth", "name": body.name.strip(),
        "status": {"$in": ["authorizing", "error"]},
    })
    # The browser's own origin (behind a proxy, the forwarded one) is where the
    # vendor must send the person back.
    origin = request.headers.get("origin") or request.headers.get("referer") or str(request.base_url)
    origin = origin.split("/api/")[0].rstrip("/")
    if origin.endswith("/onboarding") or origin.count("/") > 2:
        origin = "/".join(origin.split("/")[:3])
    doc = {
        "_id": uuid4().hex, "workspace_id": ws["_id"], "name": body.name.strip(),
        "kind": "mcp_oauth", "url": url, "headers": {}, "command": None, "args": [],
        "allow_write": body.allow_write, "disabled_tools": [], "tools": [],
        "status": "authorizing", "error_message": None, "oauth": {"origin": origin},
        "created_at": now, "created_by": user["id"], "uses": 0,
    }
    await db.tool_grants.insert_one(doc)
    oauth.start_connect(doc)
    auth_url = await asyncio.to_thread(oauth.wait_for_auth_url, doc["_id"], 40.0)
    if not auth_url:
        fresh = await db.tool_grants.find_one({"_id": doc["_id"]})
        detail = (fresh or {}).get("error_message") or "The server did not offer a login within 40 seconds. Check the URL."
        await db.tool_grants.delete_one({"_id": doc["_id"]})
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)
    await pool.drop(ws["_id"])
    return {"grant_id": doc["_id"], "auth_url": auth_url}


@router.get("/oauth/callback/{grant_id}", response_class=HTMLResponse)
async def oauth_callback(grant_id: str, code: str | None = None, state: str | None = None,
                         error: str | None = None, error_description: str | None = None,
                         db=Depends(get_db)):
    """Where the vendor sends the person back. Public by necessity; the code is
    single-use and only the worker waiting on this grant can spend it."""
    if error or not code:
        msg = error_description or error or "no code returned"
        await db.tool_grants.update_one({"_id": grant_id}, {"$set": {"status": "error", "error_message": f"Login refused: {msg}"}})
        body = f"<h2>Login did not complete</h2><p>{msg}</p><p>You can close this window.</p>"
    else:
        delivered = oauth.deliver_code(grant_id, code, state)
        body = ("<h2>Connected</h2><p>Sensei is finishing the connection. You can close this window.</p>"
                if delivered else "<h2>This login has expired</h2><p>Start the connection again from the Tools page.</p>")
    return f"""<!doctype html><html><body style="font-family:system-ui;padding:40px;color:#222">
{body}<script>
try {{ if (window.opener) {{ window.opener.postMessage({{type: 'sensei-oauth', grant_id: '{grant_id}'}}, '*'); }} }} catch (e) {{}}
setTimeout(() => {{ try {{ window.close(); }} catch (e) {{}} }}, 1500);
</script></body></html>"""


@router.get("")
async def list_tools(user=Depends(get_current_user), db=Depends(get_db)):
    ws, role = await require_workspace(user, db)
    # A sign-in window closed without finishing leaves the connection waiting
    # forever. After ten minutes, say what happened so the owner can retry.
    await db.tool_grants.update_many(
        {"workspace_id": ws["_id"], "status": "authorizing",
         "created_at": {"$lt": datetime.now(timezone.utc) - timedelta(minutes=10)}},
        {"$set": {"status": "error",
                  "error_message": "The sign-in was not completed. Sign in again to finish connecting."}},
    )
    grants = await registry.load_grants(db, ws["_id"])
    is_owner = role in OWNER_ROLES
    return {
        "grants": [registry.serialize_grant(g, for_owner=is_owner) for g in grants],
        "can_manage": is_owner,
    }


@router.patch("/{grant_id}")
async def update_tool(grant_id: str, body: GrantPatch, user=Depends(get_current_user), db=Depends(get_db)):
    ws = await require_owner(user, db, "change what tools the agent may use")
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nothing to change")
    changes["updated_at"] = datetime.now(timezone.utc)
    result = await db.tool_grants.find_one_and_update(
        {"_id": grant_id, "workspace_id": ws["_id"]}, {"$set": changes}, return_document=True
    )
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such tool connection")
    return {"grant": registry.serialize_grant(result, for_owner=True)}


@router.post("/{grant_id}/test")
async def test_tool(grant_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Reconnect and refresh the tool list — servers add tools over time."""
    ws = await require_owner(user, db, "test tool connections")
    doc = await db.tool_grants.find_one({"_id": grant_id, "workspace_id": ws["_id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such tool connection")
    secret = secrets.decrypt_dict(doc.get("config_secret"))
    if isinstance(secret.get("env"), dict):
        secret["env"] = {k: secrets.decrypt(v) for k, v in secret["env"].items()}
    try:
        tools = await _probe_or_422(doc, secret)
        await pool.drop(ws["_id"])
        await db.tool_grants.update_one(
            {"_id": grant_id},
            {"$set": {"tools": tools, "status": "connected", "error_message": None,
                      "updated_at": datetime.now(timezone.utc)}},
        )
    except HTTPException as exc:
        await db.tool_grants.update_one(
            {"_id": grant_id},
            {"$set": {"status": "error", "error_message": exc.detail,
                      "updated_at": datetime.now(timezone.utc)}},
        )
        raise
    doc = await db.tool_grants.find_one({"_id": grant_id})
    return {"grant": registry.serialize_grant(doc, for_owner=True)}


@router.delete("/{grant_id}", status_code=204)
async def revoke_tool(grant_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    ws = await require_owner(user, db, "revoke tools")
    result = await db.tool_grants.delete_one({"_id": grant_id, "workspace_id": ws["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such tool connection")
    await pool.drop(ws["_id"])     # revocation takes effect on the next turn, not the next restart
