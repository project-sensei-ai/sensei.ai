"""Workspace membership — the single place that decides who may see a workspace.

A user belongs to exactly one workspace, either as its `owner` or as a `member`.
Owners manage sources; members ask questions. Every route that touches workspace
data resolves access through `require_workspace` or `require_owner` so the rule
lives in one file.
"""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status

OWNER_ROLES = {"owner", "admin"}


def member_doc(
    workspace_id: str,
    user_id: str,
    role: str,
    invited_by: str | None = None,
    status: str = "active",
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "_id": uuid4().hex,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "role": role,
        "status": status,          # invited → active once they accept
        "invited_by": invited_by,
        "invited_at": now,
        "joined_at": now if status == "active" else None,
        # Which sources this person may be answered from. None means all of
        # them, which is the sane default — an owner who wants to narrow it does
        # so deliberately, rather than having to grant access before anyone can
        # ask anything.
        "source_access": None,
    }


async def visible_sources(db, workspace_id: str, user_id: str) -> list[str] | None:
    """
    The source ids this person may be answered from, or None for all.

    Owners always see everything — they chose what to connect. For members it is
    whatever the owner set, filtered against sources that still exist, so
    deleting a source cannot leave a dangling grant.
    """
    member = await db.members.find_one({"workspace_id": workspace_id, "user_id": user_id})
    if not member or member.get("role") in OWNER_ROLES:
        return None
    allowed = member.get("source_access")
    if allowed is None:
        return None
    live = {s["_id"] async for s in db.sources.find({"workspace_id": workspace_id})}
    return [sid for sid in allowed if sid in live]


async def require_workspace(user, db) -> tuple[dict, str]:
    """
    Return (workspace, role) for the workspace this user belongs to.
    Raises 404 if they belong to none — the frontend reads that as "go onboard".
    """
    member = await db.members.find_one({"user_id": user["id"]})
    if member and member.get("status", "active") != "active":
        # Added to the allowlist but has not accepted yet.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Your invite is still pending — open the link your project owner sent you.",
        )
    if member:
        workspace = await db.workspaces.find_one({"_id": member["workspace_id"]})
        if workspace:
            return workspace, member.get("role", "member")

    # Workspaces created before the members collection existed have no member row.
    # Backfill on first access so legacy owners keep working.
    workspace = await db.workspaces.find_one({"owner_id": user["id"]})
    if workspace:
        await db.members.insert_one(member_doc(workspace["_id"], user["id"], "owner"))
        return workspace, "owner"

    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        "No workspace yet — create one, or open an invite link from your project owner",
    )


async def require_owner(user, db, action: str = "change this project") -> dict:
    """Return the workspace this user owns or administers. 403 for plain members."""
    workspace, role = await require_workspace(user, db)
    if role not in OWNER_ROLES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Only the project owner can {action}",
        )
    return workspace
