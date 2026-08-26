"""Chat routes — session management + cited Q&A via Groq."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from groq import Groq
from pydantic import BaseModel, Field

from auth.deps import get_current_user
from core.config import settings
from db.chroma import get_chroma, get_workspace_collection
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


def _answer_from_chroma(request: Request, workspace_id: str, question: str):
    """Query ChromaDB and call Groq. Returns (answer, citations)."""
    chroma = get_chroma(request)
    collection = get_workspace_collection(chroma, workspace_id)
    count = collection.count()
    if count == 0:
        return "No sources indexed yet. Add sources in the Sources page first.", []

    n = min(5, count)
    results = collection.query(
        query_texts=[question],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )
    docs = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    if not docs:
        return "I couldn't find relevant content for that question.", []

    context_parts: list[str] = []
    citations: list[dict] = []
    seen_labels: set[str] = set()
    for i, (doc, meta, dist) in enumerate(zip(docs, metadatas, distances)):
        label = (
            meta.get("source_label") or meta.get("repo") or meta.get("title")
            or meta.get("url") or "Unknown source"
        )
        context_parts.append(f"[{i + 1}] {label}\n{doc}")
        if label not in seen_labels:
            seen_labels.add(label)
            citations.append({
                "index": i + 1,
                "source_label": label,
                "excerpt": doc[:250] + ("…" if len(doc) > 250 else ""),
                "score": round(1 - float(dist), 3),
            })

    if not settings.GROQ_API_KEY:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "GROQ_API_KEY not configured")

    groq_client = Groq(api_key=settings.GROQ_API_KEY)
    completion = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Sensei, a helpful AI assistant embedded in a project knowledge platform.\n\n"
                    "Behaviour rules:\n"
                    "- For greetings, small-talk, or general questions (e.g. 'how are you', 'what can you do'): "
                    "respond naturally and helpfully from your own knowledge — do NOT reference the context.\n"
                    "- For questions about the project, code, or documentation: answer ONLY from the numbered "
                    "context passages below. Cite every claim inline with [N] matching the passage number. "
                    "If the context is insufficient, say so clearly — never fabricate.\n"
                    "- Be concise. Use markdown for code or lists when helpful."
                ),
            },
            {
                "role": "user",
                "content": f"Context passages from indexed sources:\n{'\n\n---\n\n'.join(context_parts)}\n\nQuestion: {question}",
            },
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    answer = completion.choices[0].message.content or ""
    return answer, citations


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
    answer, citations = _answer_from_chroma(request, session["workspace_id"], body.question)

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
