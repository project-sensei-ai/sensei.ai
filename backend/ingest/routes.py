from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from agent.ingest import run_ingestion
from auth.deps import get_current_user
from db.database import get_db
from db.models import serialize_source

router = APIRouter(tags=["ingest"])


async def _assert_source_ownership(source_id: str, user: dict, db) -> dict:
    """Verify the source belongs to a workspace owned by this user."""
    source = await db.sources.find_one({"_id": source_id})
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    workspace = await db.workspaces.find_one({"_id": source["workspace_id"]})
    if not workspace or workspace["owner_id"] != user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    return source


@router.post("/{source_id}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingest(
    source_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    source = await _assert_source_ownership(source_id, user, db)

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
    source = await _assert_source_ownership(source_id, user, db)
    return {
        "source_id": source_id,
        "status": source.get("status", "pending"),
        "stats": source.get("stats", {}),
        "error_message": source.get("error_message"),
    }
