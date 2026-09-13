"""Gap reports — what nobody wrote down, and drafts that close it."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from agent import usage
from agent.gaps import draft_for_gap, scan_gaps
from auth.deps import get_current_user
from db.database import get_db
from db.membership import require_owner, require_workspace
from db.models import serialize_draft, serialize_gap_report

router = APIRouter(tags=["gaps"])


@router.get("")
async def get_report(user=Depends(get_current_user), db=Depends(get_db)):
    """The latest audit of what this project has failed to write down."""
    workspace, _role = await require_workspace(user, db)
    doc = await db.gap_reports.find_one({"workspace_id": workspace["_id"]})
    return {"report": serialize_gap_report(doc) if doc else None}


@router.post("/scan", status_code=status.HTTP_202_ACCEPTED)
async def rescan(
    request: Request,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    workspace = await require_owner(user, db, "run a documentation audit")
    background_tasks.add_task(
        scan_gaps, request.app.state.mongo_db, request.app.state.chroma_client,
        workspace["_id"], True,
    )
    return {"message": "The agent is auditing the project's documentation."}


@router.post("/{gap_id}/draft", status_code=status.HTTP_202_ACCEPTED)
async def request_draft(
    gap_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Ask the agent to write the missing document. This is the decision the
    report puts to a human: it found the gap, it can close it, you say when."""
    workspace = await require_owner(user, db, "ask for a draft")
    report = await db.gap_reports.find_one({"workspace_id": workspace["_id"]})
    gap = next((g for g in (report or {}).get("gaps", []) if g.get("id") == gap_id), None)
    if not gap:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such gap in the current report")
    if not gap.get("can_draft"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "The indexed sources don't contain enough to write this one. It needs a human.",
        )
    background_tasks.add_task(
        draft_for_gap, request.app.state.mongo_db, request.app.state.chroma_client,
        workspace["_id"], gap_id,
    )
    return {"message": f"Drafting '{gap['title']}'."}


@router.get("/{gap_id}/draft")
async def get_draft(gap_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    workspace, _role = await require_workspace(user, db)
    doc = await db.drafts.find_one({"workspace_id": workspace["_id"], "gap_id": gap_id})
    return {"draft": serialize_draft(doc) if doc else None}


@router.get("/usage")
async def token_usage(user=Depends(get_current_user), db=Depends(get_db)):
    """What the agent's background work has cost this project, by operation."""
    workspace, _role = await require_workspace(user, db)
    return await usage.summary(db, workspace["_id"])
