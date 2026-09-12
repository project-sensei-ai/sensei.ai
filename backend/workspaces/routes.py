import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from auth.deps import get_current_user
from core.config import settings
from db.database import get_db
from db.membership import member_doc, require_workspace
from db.models import serialize_invite, serialize_workspace

router = APIRouter(tags=["workspaces"])


class WorkspaceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)


class JoinIn(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)


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
    await db.members.insert_one(member_doc(doc["_id"], user["id"], "owner"))
    return {"workspace": serialize_workspace(doc, role="owner")}


@router.get("/me")
async def get_my_workspace(
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    doc, role = await require_workspace(user, db)
    return {"workspace": serialize_workspace(doc, role=role)}


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


@router.post("/join", status_code=status.HTTP_200_OK)
async def join_workspace(
    body: JoinIn,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Accept an invite link and become a member of the inviting workspace."""
    invite = await db.invites.find_one({"token": body.token})
    if not invite:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite link is not valid")

    expires_at = invite.get("expires_at")
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status.HTTP_410_GONE, "Invite link has expired — ask for a new one")

    workspace = await db.workspaces.find_one({"_id": invite["workspace_id"]})
    if not workspace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That workspace no longer exists")

    existing = await db.members.find_one({"user_id": user["id"]})
    if existing:
        if existing["workspace_id"] == workspace["_id"]:
            # Already joined — make re-opening the link harmless.
            return {"workspace": serialize_workspace(workspace, role=existing.get("role", "member")),
                    "already_member": True}
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You already belong to a workspace. Leave it before joining another.",
        )

    await db.members.insert_one(
        member_doc(workspace["_id"], user["id"], "member", invited_by=invite.get("created_by"))
    )
    return {"workspace": serialize_workspace(workspace, role="member"), "already_member": False}
