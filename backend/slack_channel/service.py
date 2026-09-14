"""
Sensei inside Slack.

Reading a channel made Sensei informed; this makes it present. Slack sends
every message in the channels the app was added to, plus mentions and direct
messages, and the same speak-or-stay-quiet rule as everywhere else decides
what happens: a mention or a direct message is always answered, a question
the project's sources can cite is answered in its thread, and everything else
is left alone. Messages in a synced channel are indexed as they arrive, so a
decision posted at 10:02 can be asked about at 10:03.
"""
import asyncio
import hashlib
import hmac
import re
import time
from collections import OrderedDict
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from agent.tools import _slack_message_doc, relevant_citations
from channels.base import Channel, IncomingMessage
from channels.router import Mode, decide, should_post
from core import secrets
from core.config import settings
from core.formatting import plain_answer
from db.chroma import get_workspace_collection

SLACK_API = "https://slack.com/api"


# ── Request authenticity ─────────────────────────────────────────────────────

def verify_signature(secret: str, timestamp: str | None, body: bytes, signature: str | None) -> bool:
    """Slack's v0 signing scheme: HMAC-SHA256 over "v0:{timestamp}:{body}", within five minutes."""
    if not (secret and timestamp and signature):
        return False
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False
    digest = "v0=" + hmac.new(secret.encode(), f"v0:{timestamp}:".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


# ── Text in and out ──────────────────────────────────────────────────────────

_MENTION = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]*)?>")
_BY_NAME = re.compile(r"(?i)^(?:hey |hi |ok |hello )?sensei\b[,:!]?\s*")


def strip_mentions(text: str, bot_user_id: str | None) -> tuple[str, bool]:
    """The message without the <@U…> tokens, and whether one of them was Sensei."""
    text = text or ""
    mentioned = bool(bot_user_id) and bot_user_id in _MENTION.findall(text)
    cleaned = re.sub(r"\s+", " ", _MENTION.sub("", text)).strip(" ,:;-")
    if _BY_NAME.match(cleaned):
        mentioned = True
        cleaned = _BY_NAME.sub("", cleaned)
    return cleaned, mentioned


def to_mrkdwn(text: str) -> str:
    """Slack bolds with single asterisks and has no markdown bullets."""
    out = []
    for line in (text or "").split("\n"):
        line = re.sub(r"\*\*(.+?)\*\*", r"*\1*", line)
        line = re.sub(r"^(\s*)- ", r"\1• ", line)
        out.append(line)
    return "\n".join(out)


# ── Which project a message belongs to ───────────────────────────────────────

_IDENTITY: dict[str, dict] = {}
_NAMES: dict[str, str] = {}


async def _identity(source: dict) -> dict | None:
    """The team and bot user behind a Slack source, cached for an hour."""
    cached = _IDENTITY.get(source["_id"])
    if cached and time.time() - cached["at"] < 3600:
        return cached
    token = (secrets.decrypt_dict(source.get("config_secret") or {}) or {}).get("token")
    if not token:
        return None
    async with httpx.AsyncClient(timeout=15, headers={"Authorization": f"Bearer {token}"}) as c:
        payload = (await c.post(f"{SLACK_API}/auth.test")).json()
    if not payload.get("ok"):
        return None
    cfg = source.get("config") or {}
    ident = {
        "source_id": source["_id"], "workspace_id": source["workspace_id"], "token": token,
        "team_id": payload.get("team_id"), "bot_user_id": payload.get("user_id"),
        "channel_id": cfg.get("channel_id"), "channel_name": cfg.get("channel_name"),
        "team_domain": cfg.get("team_domain"), "at": time.time(),
    }
    _IDENTITY[source["_id"]] = ident
    return ident


async def _display_name(token: str, user_id: str | None) -> str:
    if not user_id:
        return "someone"
    if user_id in _NAMES:
        return _NAMES[user_id]
    name = user_id
    try:
        async with httpx.AsyncClient(timeout=10, headers={"Authorization": f"Bearer {token}"}) as c:
            payload = (await c.get(f"{SLACK_API}/users.info", params={"user": user_id})).json()
        if payload.get("ok"):
            profile = payload["user"].get("profile") or {}
            name = profile.get("display_name") or profile.get("real_name") or payload["user"].get("name") or user_id
    except Exception:
        pass
    _NAMES[user_id] = name
    return name


# ── Once per event ───────────────────────────────────────────────────────────

_SEEN: OrderedDict[str, float] = OrderedDict()


def already_seen(key: str) -> bool:
    if key in _SEEN:
        return True
    _SEEN[key] = time.time()
    while len(_SEEN) > 5000:
        _SEEN.popitem(last=False)
    return False


# ── The work ─────────────────────────────────────────────────────────────────

async def index_live_message(db, chroma_client, ident: dict, event: dict) -> None:
    """A message in a synced channel joins the index the moment it is posted."""
    from agent.ingest import _chunk_text, _context_header
    source = await db.sources.find_one({"_id": ident["source_id"]})
    if not source:
        return
    name = await _display_name(ident["token"], event.get("user"))
    doc = _slack_message_doc(event, ident["channel_name"], ident["team_domain"], ident["channel_id"],
                             {event.get("user"): name}, "reply" if event.get("thread_ts") else "message")
    header = _context_header(source["label"], doc["metadata"])
    ids, documents, metadatas = [], [], []
    for i, chunk in enumerate(_chunk_text(doc["content"])):
        ids.append(f"{source['_id']}_live_{str(event.get('ts', '')).replace('.', '_')}_{i}")
        documents.append(header + chunk)
        metadatas.append({**doc["metadata"], "source_id": source["_id"], "source_label": source["label"], "chunk": -1})
    if not ids:
        return
    get_workspace_collection(chroma_client, source["workspace_id"]).upsert(ids=ids, documents=documents, metadatas=metadatas)
    await db.sources.update_one({"_id": source["_id"]}, {
        "$inc": {"stats.chunks_count": len(ids), "stats.pages_crawled": 1},
        "$set": {"updated_at": datetime.now(timezone.utc)},
    })


async def answer_in_workspace(db, chroma_client, workspace_id: str, question: str) -> tuple[str, list[dict]]:
    """The same colleague the web chat gets, reading everything the owner shared, with no write tools."""
    from agent.agent import build_colleague
    from chat.routes import _primed
    workspace = await db.workspaces.find_one({"_id": workspace_id}) or {}
    sources = [s async for s in db.sources.find({"workspace_id": workspace_id})]
    col = await asyncio.to_thread(
        build_colleague, workspace_id, chroma_client,
        sources=sources, grants=[], user_id=workspace.get("owner_id") or "slack",
        allowed_sources=None, question=question,
    )
    try:
        passages = await asyncio.to_thread(col.search, query=question)
        result = await col.agent.invoke_async(_primed(question, passages))
        answer = plain_answer(str(result))
        citations = relevant_citations(list(col.citations), answer)
    finally:
        col.close()
    return answer, citations


async def post_reply(token: str, channel: str, answer: str, citations: list[dict], thread_ts: str | None = None) -> str | None:
    text = to_mrkdwn(answer)
    titles = list(dict.fromkeys((c.get("title") or c.get("source_label") or "").strip() for c in citations))
    titles = [t for t in titles if t][:3]
    if titles:
        text += "\n_Sources: " + ", ".join(titles) + "_"
    body = {"channel": channel, "text": text, "unfurl_links": False, "unfurl_media": False}
    if thread_ts:
        body["thread_ts"] = thread_ts
    async with httpx.AsyncClient(timeout=15, headers={"Authorization": f"Bearer {token}"}) as c:
        payload = (await c.post(f"{SLACK_API}/chat.postMessage", json=body)).json()
    if not payload.get("ok"):
        raise RuntimeError(f"Slack chat.postMessage failed: {payload.get('error')}")
    return payload.get("ts")


async def record_gap(db, workspace_id: str, question: str, author: str) -> None:
    from answers import store as answer_store
    await answer_store.record(db, workspace_id, question, {"id": f"slack:{author}", "name": f"{author} (Slack)", "email": None}, "slack")


async def handle_event(db, chroma_client, payload: dict) -> dict:
    """Decide, answer, post, remember. Returns what happened and why, for the record."""
    from answers.store import is_worth_recording

    event = payload.get("event") or {}
    kind = event.get("type")
    if kind not in ("app_mention", "message"):
        return {"outcome": "ignored", "reason": f"event type {kind}"}
    if event.get("subtype") or event.get("bot_id"):
        return {"outcome": "ignored", "reason": "not a person's message"}
    channel, ts = event.get("channel"), event.get("ts")
    team_id = payload.get("team_id") or event.get("team")
    if not (channel and ts):
        return {"outcome": "ignored", "reason": "no channel or timestamp"}
    if already_seen(payload.get("event_id") or f"{kind}:{team_id}:{channel}:{ts}"):
        return {"outcome": "ignored", "reason": "duplicate delivery"}

    idents = []
    async for source in db.sources.find({"type": "slack"}):
        try:
            ident = await _identity(source)
        except Exception as exc:
            # One project's unreadable token must not silence every other project.
            print(f"[slack] skipping source {source.get('_id')}: {exc}")
            continue
        if ident and ident["team_id"] == team_id:
            idents.append(ident)
    if not idents:
        return {"outcome": "ignored", "reason": "no project is connected to this Slack team"}
    ident = next((i for i in idents if i["channel_id"] == channel), idents[0])
    if event.get("user") == ident["bot_user_id"]:
        return {"outcome": "ignored", "reason": "Sensei's own message"}

    text, mentioned = strip_mentions(event.get("text") or "", ident["bot_user_id"])
    if kind == "message" and mentioned and event.get("channel_type") != "im":
        # Slack delivers a mention twice: as app_mention and as message. One is enough.
        return {"outcome": "ignored", "reason": "handled as a mention"}
    direct = event.get("channel_type") == "im"
    mentioned = mentioned or kind == "app_mention" or direct

    indexed = False
    if ident["channel_id"] == channel and not direct:
        try:
            await index_live_message(db, chroma_client, ident, event)
            indexed = True
        except Exception as exc:
            print(f"[slack] live index failed: {exc}")

    incoming = IncomingMessage(
        channel=Channel.SLACK, workspace_id=ident["workspace_id"], conversation_id=channel, message_id=ts,
        text=text, author_id=event.get("user") or "", author_name=event.get("user") or "",
        mentioned_agent=mentioned, is_reply=bool(event.get("thread_ts")), raw=event,
    )
    decision = decide(incoming, get_workspace_collection(chroma_client, ident["workspace_id"]))
    if decision.mode is Mode.PROACTIVE and not settings.SLACK_PROACTIVE:
        decision = type(decision)(Mode.SILENT, "unprompted answers are switched off", decision.confidence)

    record = {
        "_id": uuid4().hex, "workspace_id": ident["workspace_id"], "channel": channel, "channel_name": ident["channel_name"],
        "ts": ts, "author": event.get("user") or "", "text": text[:500], "mode": decision.mode.value,
        "reason": decision.reason, "indexed": indexed, "posted": False, "answer": "", "citations": [],
        "at": datetime.now(timezone.utc),
    }
    if not decision.should_respond:
        await db.slack_replies.insert_one(record)
        return {"outcome": "silent", "reason": decision.reason}

    answer, citations = await answer_in_workspace(db, chroma_client, ident["workspace_id"], text)
    post, why = should_post(answer, citations, decision.mode)
    record.update({"answer": answer, "citations": citations[:5], "reason": why})
    if post:
        thread = event.get("thread_ts") or (None if direct else ts)
        await post_reply(ident["token"], channel, answer, citations, thread_ts=thread)
        record["posted"] = True
    if decision.mode is Mode.MENTIONED and is_worth_recording(text, answer, citations):
        try:
            await record_gap(db, ident["workspace_id"], text, event.get("user") or "someone")
        except Exception as exc:
            print(f"[slack] could not record the gap: {exc}")
    await db.slack_replies.insert_one(record)
    return {"outcome": "posted" if post else "silent", "reason": why, "answer": answer}
