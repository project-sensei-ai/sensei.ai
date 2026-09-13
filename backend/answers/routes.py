"""The answer ledger — what the agent couldn't answer, and closing it."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from answers import store
from auth.deps import get_current_user
from db.chroma import get_chroma
from db.database import get_db
from db.membership import OWNER_ROLES, require_owner, require_workspace
from db.models import serialize_unanswered

router = APIRouter(tags=["answers"])


class AnswerIn(BaseModel):
    text: str = Field(..., min_length=2, max_length=4000)


@router.get("")
async def ledger(user=Depends(get_current_user), db=Depends(get_db)):
    """
    Questions the agent could not answer.

    Members see what they themselves asked — useful, and it avoids turning the
    ledger into a public record of who did not know what. Owners see all of it,
    because they are the ones who can close them.
    """
    workspace, role = await require_workspace(user, db)
    query = {"workspace_id": workspace["_id"]}
    if role not in OWNER_ROLES:
        query["asked_by_id"] = user["id"]

    entries = [
        e async for e in db.unanswered.find(query).sort(
            [("status", 1), ("times_asked", -1), ("last_asked_at", -1)]
        ).limit(60)
    ]
    return {
        "entries": [serialize_unanswered(e) for e in entries],
        "can_answer": role in OWNER_ROLES,
        "stats": await store.stats(db, workspace["_id"]),
    }


@router.post("/{entry_id}")
async def answer_it(
    entry_id: str,
    body: AnswerIn,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Answer once; the agent knows it from then on."""
    workspace = await require_owner(user, db, "answer questions for the whole team")
    result = await store.answer(
        db, get_chroma(request), workspace["_id"], entry_id, body.text, user
    )
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such question")
    return {"entry": serialize_unanswered(result),
            "message": "Indexed. The agent can answer this now."}


@router.delete("/{entry_id}", status_code=204)
async def dismiss(entry_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Not everything asked deserves documenting."""
    workspace = await require_owner(user, db, "dismiss questions")
    res = await db.unanswered.update_one(
        {"_id": entry_id, "workspace_id": workspace["_id"]},
        {"$set": {"status": "dismissed"}},
    )
    if res.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such question")
