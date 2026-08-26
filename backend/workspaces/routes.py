import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from auth.deps import get_current_user
from core.config import settings
from db.database import get_db
from db.models import serialize_invite, serialize_workspace

router = APIRouter(tags=["workspaces"])


class WorkspaceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: WorkspaceIn,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    existing = await db.workspaces.find_one({"owner_id": user["id"]})
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Workspace already exists")

    doc = {
        "_id": uuid4().hex,
        "owner_id": user["id"],
        "name": body.name,
        "description": body.description,
        "created_at": datetime.now(timezone.utc),
    }
    await db.workspaces.insert_one(doc)
    return {"workspace": serialize_workspace(doc)}


@router.get("/me")
async def get_my_workspace(
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    doc = await db.workspaces.find_one({"owner_id": user["id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No workspace found")
    return {"workspace": serialize_workspace(doc)}


@router.post("/{workspace_id}/invite", status_code=status.HTTP_201_CREATED)
async def generate_invite(
    workspace_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    workspace = await db.workspaces.find_one({"_id": workspace_id})
    if not workspace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    if workspace["owner_id"] != user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not the workspace owner")

    token = secrets.token_urlsafe(24)
    invite_url = f"{settings.FRONTEND_ORIGIN}/join?token={token}"
    now = datetime.now(timezone.utc)
    doc = {
        "_id": uuid4().hex,
        "workspace_id": workspace_id,
        "token": token,
        "invite_url": invite_url,
        "created_by": user["id"],
        "created_at": now,
        "expires_at": now + timedelta(days=7),
    }
    await db.invites.insert_one(doc)
    return {"invite": serialize_invite(doc)}
