"""Onboarding briefs — the agent's unprompted work, read back."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from agent.brief import generate_brief
from auth.deps import get_current_user
from db.database import get_db
from db.membership import OWNER_ROLES, require_workspace
from db.models import serialize_brief

router = APIRouter(tags=["briefs"])


@router.get("/me")
async def my_brief(user=Depends(get_current_user), db=Depends(get_db)):
    """The brief written for the caller, if the agent has produced one."""
    workspace, _role = await require_workspace(user, db)
    doc = await db.briefs.find_one({"workspace_id": workspace["_id"], "user_id": user["id"]})
    if not doc:
        return {"brief": None}
    return {"brief": serialize_brief(doc)}


@router.get("")
async def list_briefs(user=Depends(get_current_user), db=Depends(get_db)):
    """Every brief in the project. Owners see the team's; members see their own."""
    workspace, role = await require_workspace(user, db)
    query = {"workspace_id": workspace["_id"]}
    if role not in OWNER_ROLES:
        query["user_id"] = user["id"]
    docs = [d async for d in db.briefs.find(query).sort("created_at", -1)]
    return {"briefs": [serialize_brief(d) for d in docs]}


@router.post("/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str | None = None,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Re-run the research and rewrite a brief. Owners may target anyone on the
    project; everyone else may only refresh their own.
    """
    workspace, role = await require_workspace(user, db)
    target = user_id or user["id"]
    if target != user["id"] and role not in OWNER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the project owner can refresh someone else's brief")

    member = await db.members.find_one({"workspace_id": workspace["_id"], "user_id": target})
    if not member:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That person is not on this project")

    background_tasks.add_task(
        generate_brief,
        request.app.state.mongo_db,
        request.app.state.chroma_client,
        workspace["_id"],
        target,
    )
    return {"message": "The agent is researching the project. This takes a few minutes.", "user_id": target}
