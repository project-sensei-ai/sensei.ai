"""Readiness — the self-interview, read and re-run."""
from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from agent.readiness import run_readiness, serialize
from auth.deps import get_current_user
from db.database import get_db
from db.membership import require_owner, require_workspace

router = APIRouter(tags=["readiness"])


@router.get("")
async def get_readiness(user=Depends(get_current_user), db=Depends(get_db)):
    ws, _ = await require_workspace(user, db)
    return {"readiness": serialize(await db.readiness.find_one({"workspace_id": ws["_id"]}))}


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def rerun(request: Request, background: BackgroundTasks,
                user=Depends(get_current_user), db=Depends(get_db)):
    ws = await require_owner(user, db, "re-run the self-check")
    background.add_task(run_readiness, request.app.state.mongo_db, request.app.state.chroma_client,
                        ws["_id"], True)
    return {"message": "Sensei is interviewing itself. A minute or so."}
