from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from agent.ingest import run_ingestion
from auth.deps import get_current_user
from db.database import get_db
from db.membership import OWNER_ROLES, require_workspace

router = APIRouter(tags=["ingest"])


async def _readable_source(source_id: str, user: dict, db, owner_only: bool = False) -> dict:
    """
    Fetch a source the caller may see: it must belong to the caller's workspace.
    With owner_only, plain members are rejected — they may watch ingestion status
    but not start it.
    """
    workspace, role = await require_workspace(user, db)
    source = await db.sources.find_one({"_id": source_id, "workspace_id": workspace["_id"]})
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    if owner_only and role not in OWNER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the project owner can start ingestion")
    return source


@router.post("/{source_id}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingest(
    source_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    source = await _readable_source(source_id, user, db, owner_only=True)

    if source["status"] == "indexing":
        raise HTTPException(status.HTTP_409_CONFLICT, "Ingestion already running")

    background_tasks.add_task(
        run_ingestion,
        request.app.state.mongo_db,
        request.app.state.chroma_client,
        source_id,
    )
    return {"message": "Ingestion started", "source_id": source_id}


@router.get("/{source_id}/status")
async def ingest_status(
    source_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    source = await _readable_source(source_id, user, db)
    return {
        "source_id": source_id,
        "status": source.get("status", "pending"),
        "stats": source.get("stats", {}),
        "error_message": source.get("error_message"),
    }
