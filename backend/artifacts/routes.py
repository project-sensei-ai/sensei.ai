"""Files the agent produced — downloadable by anyone on the same project."""
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from auth.deps import get_current_user
from db.database import get_db
from db.membership import require_workspace
from db.models import _iso

router = APIRouter(tags=["artifacts"])


def serialize_artifact(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "title": doc.get("title"),
        "filename": doc.get("filename"),
        "kind": doc.get("kind"),
        "mime": doc.get("mime"),
        "size": doc.get("size", 0),
        "summary": doc.get("summary"),
        "created_at": _iso(doc.get("created_at")),
        "url": f"/api/artifacts/{doc['_id']}",
    }


@router.get("")
async def list_artifacts(user=Depends(get_current_user), db=Depends(get_db)):
    ws, _ = await require_workspace(user, db)
    docs = [d async for d in db.artifacts.find({"workspace_id": ws["_id"]}).sort("created_at", -1).limit(50)]
    return {"artifacts": [serialize_artifact(d) for d in docs]}


@router.get("/{artifact_id}")
async def download(artifact_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    ws, _ = await require_workspace(user, db)
    doc = await db.artifacts.find_one({"_id": artifact_id, "workspace_id": ws["_id"]})
    if not doc or not os.path.isfile(doc.get("path", "")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That file is no longer available")
    return FileResponse(doc["path"], media_type=doc.get("mime"), filename=doc.get("filename"))
