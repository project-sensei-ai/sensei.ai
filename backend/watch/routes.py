"""Change digests — what moved, and whether it mattered."""
from fastapi import APIRouter, Depends, Request, status

from agent.watch import watch_workspace
from auth.deps import get_current_user
from db.chroma import get_chroma
from db.database import get_db
from db.membership import require_owner, require_workspace
from db.models import _iso

router = APIRouter(tags=["watch"])


@router.get("")
async def digests(user=Depends(get_current_user), db=Depends(get_db)):
    """Changes the agent judged worth reporting. Most checks produce none."""
    workspace, _role = await require_workspace(user, db)
    items = [
        {
            "id": d["_id"],
            "headline": d.get("headline"),
            "detail": d.get("detail"),
            "affects": d.get("affects", []),
            "severity": d.get("severity", "minor"),
            "sources": d.get("sources", []),
            "at": _iso(d.get("at")),
            "acknowledged": d.get("acknowledged", False),
        }
        async for d in db.change_digests.find({"workspace_id": workspace["_id"]})
        .sort("at", -1).limit(20)
    ]
    return {"digests": items}


@router.post("/check", status_code=status.HTTP_200_OK)
async def check_now(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    """
    Run a check immediately.

    Synchronous on purpose: the useful answer is often "nothing changed", and a
    background task that reports nothing is indistinguishable from one that
    never ran.
    """
    workspace = await require_owner(user, db, "check for changes")
    return await watch_workspace(db, get_chroma(request), workspace["_id"])


@router.post("/{digest_id}/ack", status_code=204)
async def acknowledge(digest_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    workspace = await require_owner(user, db, "dismiss change notices")
    await db.change_digests.update_one(
        {"_id": digest_id, "workspace_id": workspace["_id"]},
        {"$set": {"acknowledged": True}},
    )
