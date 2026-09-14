"""
Meetings — the colleague joins, listens, and speaks only when it should.

Two ways in:

    companion  — the Meetings page transcribes the room in the browser and
                 posts each finished utterance here. Works for any call, any
                 platform, with no bot to admit.
    meet_bot   — a headless browser joins a Google Meet as "Sensei", reads
                 the live captions, and posts its replies into the meeting
                 chat. Same judgement, different transport.

Either way every utterance goes through `listener.consider`, which answers
when addressed, corrects only when sure, and otherwise records why it stayed
quiet — so "why didn't it say anything" always has an answer.

When the meeting ends it is summarised (typed: decisions, action items, open
questions) and indexed as a source, so next week "what did we decide about
the rollout" is answerable, with a citation to the meeting.
"""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from auth.deps import get_current_user
from agent.agent import bench_for
from core.errors import humanise, is_quota_error, model_named_in
from db.chroma import get_chroma
from db.database import get_db
from db.membership import OWNER_ROLES, require_workspace, visible_sources
from db.models import _iso
from meetings import listener

router = APIRouter(tags=["meetings"])


class StartIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    mode: str = "companion"          # companion | meet_bot
    meet_url: str | None = None


class UtteranceIn(BaseModel):
    speaker: str = Field(..., min_length=1, max_length=80)
    text: str = Field(..., min_length=1, max_length=2000)


def serialize_meeting(doc: dict, full: bool = False) -> dict:
    out = {
        "id": doc["_id"],
        "workspace_id": doc["workspace_id"],
        "title": doc.get("title"),
        "status": doc.get("status", "live"),
        "mode": doc.get("mode", "companion"),
        "meet_url": doc.get("meet_url"),
        "bot_status": doc.get("bot_status"),
        "started_at": _iso(doc.get("started_at")),
        "ended_at": _iso(doc.get("ended_at")),
        "utterance_count": len(doc.get("transcript") or []),
        "reply_count": sum(1 for r in (doc.get("replies") or []) if r.get("kind") != "silent"),
        "summary": doc.get("summary"),
        "source_id": doc.get("source_id"),
    }
    if full:
        out["transcript"] = doc.get("transcript") or []
        out["replies"] = doc.get("replies") or []
    return out


async def _meeting(meeting_id: str, ws_id: str, db) -> dict:
    doc = await db.meetings.find_one({"_id": meeting_id, "workspace_id": ws_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such meeting")
    return doc


@router.get("")
async def list_meetings(user=Depends(get_current_user), db=Depends(get_db)):
    ws, _ = await require_workspace(user, db)
    docs = [d async for d in db.meetings.find({"workspace_id": ws["_id"]}).sort("started_at", -1).limit(30)]
    return {"meetings": [serialize_meeting(d) for d in docs]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_meeting(body: StartIn, request: Request, background: BackgroundTasks,
                        user=Depends(get_current_user), db=Depends(get_db)):
    ws, _ = await require_workspace(user, db)
    now = datetime.now(timezone.utc)
    doc = {
        "_id": uuid4().hex,
        "workspace_id": ws["_id"],
        "title": body.title.strip(),
        "mode": "meet_bot" if body.mode == "meet_bot" else "companion",
        "meet_url": (body.meet_url or "").strip() or None,
        "status": "live",
        "started_by": user["id"],
        "started_at": now,
        "transcript": [],
        "replies": [],
    }
    if doc["mode"] == "meet_bot":
        if not doc["meet_url"] or "meet.google.com" not in doc["meet_url"]:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A Google Meet link is required for the bot to join")
        doc["bot_status"] = "joining"
    await db.meetings.insert_one(doc)

    if doc["mode"] == "meet_bot":
        from meetings.meet_bot import run_bot
        background.add_task(run_bot, request.app.state.mongo_db, request.app.state.chroma_client,
                            doc["_id"], user["id"])
    return {"meeting": serialize_meeting(doc, full=True)}


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    ws, _ = await require_workspace(user, db)
    return {"meeting": serialize_meeting(await _meeting(meeting_id, ws["_id"], db), full=True)}


@router.post("/{meeting_id}/utterances")
async def hear(meeting_id: str, body: UtteranceIn, request: Request,
               user=Depends(get_current_user), db=Depends(get_db)):
    """
    One thing somebody said. Returns what the agent decided — an answer, a
    correction, or silence with its reason.
    """
    ws, _ = await require_workspace(user, db)
    doc = await _meeting(meeting_id, ws["_id"], db)
    if doc.get("status") != "live":
        raise HTTPException(status.HTTP_409_CONFLICT, "That meeting has ended")

    utterance = {"speaker": body.speaker.strip(), "text": body.text.strip(),
                 "at": datetime.now(timezone.utc).isoformat()}
    await db.meetings.update_one({"_id": meeting_id}, {"$push": {"transcript": utterance}})

    recent = (doc.get("transcript") or [])[-6:]
    context = "\n".join(f"{u['speaker']}: {u['text']}" for u in recent)
    allowed = await visible_sources(db, ws["_id"], user["id"])
    reply = None
    for attempt in range(2):
        try:
            reply = await listener.consider(ws["_id"], get_chroma(request), utterance["text"], context, allowed)
            break
        except Exception as exc:
            if attempt == 0 and is_quota_error(exc):
                bench_for(exc, background=True)
                continue
            reply = listener.Reply(kind="silent", reason=f"could not judge it: {humanise(exc)}", trigger=utterance["text"])
    if reply is None:
        reply = listener.Reply(kind="silent", reason="could not judge it", trigger=utterance["text"])

    reply_doc = {"_id": uuid4().hex, **reply.to_doc()}
    await db.meetings.update_one({"_id": meeting_id}, {"$push": {"replies": reply_doc}})
    return {"utterance": utterance, "reply": {"id": reply_doc["_id"], **reply.to_doc()}}


async def _finish(db, chroma_client, meeting_id: str) -> None:
    """Summarise, then index the meeting as a source so it can be cited later."""
    from agent.ingest import run_ingestion
    doc = await db.meetings.find_one({"_id": meeting_id})
    if not doc:
        return
    transcript = doc.get("transcript") or []
    summary = None
    if transcript:
        try:
            summary = await listener.summarise(doc.get("title", "Meeting"), transcript)
        except Exception as exc:
            print(f"[meetings] summary failed: {exc}")
    held_at = _iso(doc.get("started_at")) or ""
    text = listener.transcript_as_document(doc.get("title", "Meeting"), held_at, transcript, summary,
                                           doc.get("replies") or [])

    now = datetime.now(timezone.utc)
    source = {
        "_id": uuid4().hex,
        "workspace_id": doc["workspace_id"],
        "type": "meeting",
        "label": f"Meeting: {doc.get('title', 'Meeting')} ({held_at[:10]})",
        "config": {"title": doc.get("title"), "held_at": held_at, "transcript": text, "meeting_id": meeting_id},
        "status": "pending", "stats": {}, "created_at": now, "updated_at": now,
    }
    if transcript:
        await db.sources.insert_one(source)
    await db.meetings.update_one(
        {"_id": meeting_id},
        {"$set": {"summary": summary.model_dump() if summary else None,
                  "source_id": source["_id"] if transcript else None}},
    )
    if transcript:
        await run_ingestion(db, chroma_client, source["_id"])


@router.post("/{meeting_id}/end")
async def end_meeting(meeting_id: str, request: Request, background: BackgroundTasks,
                      user=Depends(get_current_user), db=Depends(get_db)):
    ws, _ = await require_workspace(user, db)
    doc = await _meeting(meeting_id, ws["_id"], db)
    if doc.get("status") == "ended":
        return {"meeting": serialize_meeting(doc, full=True)}
    await db.meetings.update_one(
        {"_id": meeting_id},
        {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc), "bot_status": "leaving"}},
    )
    background.add_task(_finish, request.app.state.mongo_db, request.app.state.chroma_client, meeting_id)
    doc = await db.meetings.find_one({"_id": meeting_id})
    return {"meeting": serialize_meeting(doc, full=True)}


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(meeting_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    ws, role = await require_workspace(user, db)
    doc = await _meeting(meeting_id, ws["_id"], db)
    if role not in OWNER_ROLES and doc.get("started_by") != user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner or whoever started it can delete a meeting")
    await db.meetings.delete_one({"_id": meeting_id})
