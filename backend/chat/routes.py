"""Chat routes — session management + the colleague answering, streamed."""
import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.agent import build_colleague, make_session_manager
from answers import store as answer_store
from artifacts.routes import serialize_artifact
from auth.deps import get_current_user
from core.errors import humanise, is_quota_error, model_named_in
from agent.agent import mark_exhausted
from db.chroma import get_chroma
from db.database import get_db
from db.membership import require_workspace, visible_sources
from db.models import serialize_chat_session
from toolgrants import registry as grants
from toolgrants import pool

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _require_session(session_id: str, user, db):
    session = await db.chat_sessions.find_one({"_id": session_id, "owner_id": user["id"], "archived": False})
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


async def _equip(db, chroma, session: dict, user: dict, session_id: str, question: str = ""):
    """
    Everything one turn needs, resolved before the model runs: which sources
    this person may be answered from, which tools the owner granted, and which
    Atlassian credential (if any) makes Jira live.
    """
    ws = session["workspace_id"]
    allowed = await visible_sources(db, ws, user["id"])
    sources = [s async for s in db.sources.find({"workspace_id": ws})]
    grant_docs = await grants.load_grants(db, ws)
    grant_session = await pool.get_session(ws, grant_docs)
    col = await asyncio.to_thread(
        build_colleague,
        ws, chroma,
        sources=sources, grants=grant_docs, user_id=user["id"],
        session_manager=make_session_manager(session_id), allowed_sources=allowed,
        question=question, grant_session=grant_session,
    )
    return col


async def _persist_turn(db, session: dict, session_id: str, question: str, answer: str,
                        citations: list, artifacts: list, user: dict, tools_used: list[str]) -> list[dict]:
    """Store the exchange, the files it produced, and — if it went unanswered — the question."""
    now = datetime.now(timezone.utc).isoformat()
    saved = []
    for art in artifacts:
        art = {**art, "session_id": session_id}
        await db.artifacts.insert_one(art)
        saved.append(serialize_artifact(art))

    is_first = len(session.get("messages", [])) == 0
    title_update = {"title": question[:60] + ("…" if len(question) > 60 else "")} if is_first else {}
    await db.chat_sessions.update_one(
        {"_id": session_id},
        {
            "$set": {"updated_at": datetime.now(timezone.utc), **title_update},
            "$push": {"messages": {"$each": [
                {"role": "user", "content": question, "created_at": now},
                {"role": "assistant", "content": answer, "citations": citations,
                 "artifacts": saved, "tools_used": tools_used, "created_at": now},
            ]}},
        },
    )
    for name in tools_used:
        await grants.touch(db, session["workspace_id"], name)

    # An uncited answer is an ungrounded one — unless the turn was *work*
    # (a file, a live lookup, a tool action), where citations are beside the point.
    did_work = bool(artifacts) or any(
        n in ("jira_search", "jira_issue") or "_" in n and not n.startswith(("search_", "list_", "who_"))
        for n in tools_used
    )
    if not did_work and answer_store.is_worth_recording(question, answer, citations):
        await answer_store.record(db, session["workspace_id"], question, user, session_id)
    return saved


# ── Session endpoints ──────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(user=Depends(get_current_user), db=Depends(get_db)):
    ws, _role = await require_workspace(user, db)
    cursor = db.chat_sessions.find(
        {"workspace_id": ws["_id"], "owner_id": user["id"], "archived": False}
    ).sort("updated_at", -1).limit(50)
    sessions = await cursor.to_list(50)
    return {"sessions": [serialize_chat_session(s) for s in sessions]}


@router.post("/sessions", status_code=201)
async def create_session(user=Depends(get_current_user), db=Depends(get_db)):
    ws, _role = await require_workspace(user, db)
    now = datetime.now(timezone.utc)
    session_id = str(uuid4()).replace("-", "")
    doc = {
        "_id": session_id,
        "workspace_id": ws["_id"],
        "owner_id": user["id"],
        "title": "New chat",
        "messages": [],
        "created_at": now,
        "updated_at": now,
        "archived": False,
    }
    await db.chat_sessions.insert_one(doc)
    return {"session": serialize_chat_session(doc)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    session = await _require_session(session_id, user, db)
    return {"session": serialize_chat_session(session, include_messages=True)}


@router.delete("/sessions/{session_id}", status_code=204)
async def archive_session(session_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    result = await db.chat_sessions.update_one(
        {"_id": session_id, "owner_id": user["id"]},
        {"$set": {"archived": True, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    body: ChatRequest,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """One-shot answer. The streaming route below is what the UI uses."""
    session = await _require_session(session_id, user, db)
    col = await _equip(db, get_chroma(request), session, user, session_id, body.question)
    tools_used: list[str] = []
    try:
        # Strands Agent.__call__ is synchronous — run it in a thread pool
        response = await asyncio.to_thread(col.agent, body.question)
        answer = str(response)
        for m in getattr(col.agent, "messages", []) or []:
            for block in m.get("content", []) if isinstance(m, dict) else []:
                if isinstance(block, dict) and "toolUse" in block:
                    tools_used.append(block["toolUse"].get("name", ""))
    finally:
        col.close()

    artifacts = await _persist_turn(db, session, session_id, body.question, answer,
                                    col.citations, col.artifacts, user, tools_used)
    return {"answer": answer, "citations": col.citations, "artifacts": artifacts}


# ── Streaming ─────────────────────────────────────────────────────────────────
#
# The non-streaming route above answers in one lump, which means a spinner for
# up to forty seconds while the agent searches, reads and reasons. All of that
# work is interesting — it is the evidence that there is an agent here at all —
# and hiding it behind a spinner throws it away.

def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@router.post("/sessions/{session_id}/stream")
async def stream_message(
    session_id: str,
    body: ChatRequest,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Answer over server-sent events: tool calls as they happen, then the answer
    token by token, then citations and any files produced.
    """
    session = await _require_session(session_id, user, db)
    chroma = get_chroma(request)

    async def events():
        answer_parts: list[str] = []
        announced: set[str] = set()
        tools_used: list[str] = []
        col = None
        try:
            # Resolved before the stream opens; an auth question should not be
            # answered halfway through a response.
            col = await _equip(db, chroma, session, user, session_id, body.question)
            for u in col.unavailable:
                yield _sse({"type": "notice",
                            "message": f"{u['grant']} is not answering right now, so its tools are unavailable this turn."})

            # One retry on a daily-quota error, on the next model with quota
            # left. A demo should not go dark because one model's day ran out.
            for attempt in range(2):
                try:
                    async for chunk in col.agent.stream_async(body.question):
                        # A tool starting. Announced once per invocation, not once
                        # per streamed fragment of its arguments.
                        tool = chunk.get("current_tool_use")
                        if tool and tool.get("toolUseId") not in announced:
                            announced.add(tool["toolUseId"])
                            name = tool.get("name", "")
                            tools_used.append(name)
                            yield _sse({
                                "type": "tool",
                                "name": name,
                                "label": col.narration.get(name, f"Using {name.replace('_', ' ')}"),
                            })

                        text = chunk.get("data")
                        if text:
                            answer_parts.append(text)
                            yield _sse({"type": "text", "delta": text})
                    break
                except Exception as exc:
                    if attempt == 0 and is_quota_error(exc) and not answer_parts:
                        mark_exhausted(model_named_in(exc) or getattr(getattr(col.agent, "model", None), "config", {}).get("model_id"))
                        col.close()
                        yield _sse({"type": "notice", "message": "One model hit its daily limit — switching to another."})
                        col = await _equip(db, chroma, session, user, session_id, body.question)
                        continue
                    raise

            answer = "".join(answer_parts)
            col.close()
            artifacts = await _persist_turn(db, session, session_id, body.question, answer,
                                            col.citations, col.artifacts, user, tools_used)
            yield _sse({"type": "done", "citations": col.citations, "artifacts": artifacts,
                        "refusals": col.refusals})

        except Exception as exc:
            # The stream has already started, so an HTTP error code is no longer
            # available — the failure has to travel as an event.
            yield _sse({"type": "error", "message": humanise(exc)})
        finally:
            if col is not None:
                col.close()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # stop proxies holding the stream back
        },
    )
