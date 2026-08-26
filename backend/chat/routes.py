"""Chat routes — session management + Strands Agent cited Q&A."""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from agent.agent import build_agent, make_session_manager
from auth.deps import get_current_user
from db.chroma import get_chroma
from db.database import get_db
from db.models import serialize_chat_session

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _require_workspace(user, db):
    ws = await db.workspaces.find_one({"owner_id": user["id"]})
    if not ws:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No workspace — complete onboarding first")
    return ws


async def _require_session(session_id: str, user, db):
    session = await db.chat_sessions.find_one({"_id": session_id, "owner_id": user["id"], "archived": False})
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


# ── Session endpoints ──────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(user=Depends(get_current_user), db=Depends(get_db)):
    ws = await _require_workspace(user, db)
    cursor = db.chat_sessions.find(
        {"workspace_id": ws["_id"], "archived": False}
    ).sort("updated_at", -1).limit(50)
    sessions = await cursor.to_list(50)
    return {"sessions": [serialize_chat_session(s) for s in sessions]}


@router.post("/sessions", status_code=201)
async def create_session(user=Depends(get_current_user), db=Depends(get_db)):
    ws = await _require_workspace(user, db)
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
    session = await _require_session(session_id, user, db)
    chroma = get_chroma(request)

    sm = make_session_manager(session_id)
    agent, captured = build_agent(session["workspace_id"], chroma, session_manager=sm)

    # Strands Agent.__call__ is synchronous — run it in a thread pool
    response = await asyncio.to_thread(agent, body.question)
    answer = str(response)
    citations = captured  # populated in-place by search_project_docs tool calls

    now = datetime.now(timezone.utc).isoformat()
    user_msg = {"role": "user", "content": body.question, "created_at": now}
    ai_msg = {"role": "assistant", "content": answer, "citations": citations, "created_at": now}

    is_first = len(session.get("messages", [])) == 0
    title_update = {}
    if is_first:
        title_update = {"title": body.question[:60] + ("…" if len(body.question) > 60 else "")}

    await db.chat_sessions.update_one(
        {"_id": session_id},
        {
            "$set": {"updated_at": datetime.now(timezone.utc), **title_update},
            "$push": {"messages": {"$each": [user_msg, ai_msg]}},
        },
    )
    return {"answer": answer, "citations": citations}
