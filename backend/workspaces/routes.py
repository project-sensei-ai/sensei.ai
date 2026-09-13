import secrets
import uuid
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from agent.brief import generate_brief
from auth.deps import get_current_user
from core import mailer
from core.config import settings
from db.database import get_db
from db.membership import member_doc, require_owner, require_workspace
from db.models import serialize_member, serialize_workspace

INVITE_TTL_DAYS = 7

router = APIRouter(tags=["workspaces"])


class WorkspaceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)


class JoinIn(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)


class AddMembersIn(BaseModel):
    emails: list[EmailStr] = Field(..., min_length=1, max_length=25)


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

    # The token is bound to one address. Holding the link is not enough — the
    # signed-in account must be the one the owner put on the allowlist.
    if invite.get("email") and invite["email"].lower() != user["email"].lower():
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"This invite was issued to {invite['email']}. Sign in as that account to accept it.",
        )

    existing = await db.members.find_one({"user_id": user["id"]})
    if existing and existing["workspace_id"] == workspace["_id"]:
        if existing.get("status") != "active":
            await db.members.update_one(
                {"_id": existing["_id"]},
                {"$set": {"status": "active", "joined_at": datetime.now(timezone.utc)}},
            )
        await db.invites.update_one(
            {"_id": invite["_id"]}, {"$set": {"accepted_at": datetime.now(timezone.utc)}}
        )
        return {"workspace": serialize_workspace(workspace, role=existing.get("role", "member")),
                "already_member": True}
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You already belong to a workspace. Leave it before joining another.",
        )

    await db.members.insert_one(
        member_doc(workspace["_id"], user["id"], "member",
                   invited_by=invite.get("created_by"), status="active")
    )
    await db.invites.update_one(
        {"_id": invite["_id"]}, {"$set": {"accepted_at": datetime.now(timezone.utc)}}
    )
    return {"workspace": serialize_workspace(workspace, role="member"), "already_member": False}


# ── Team members — the owner's allowlist ──────────────────────────────────────
#
# Nobody reaches a project unless the owner put their address here first. An
# invite link on its own is not authorisation: the token is bound to one address
# and one workspace, and it is spent on first use.

def _invite_url(token: str) -> str:
    return f"{settings.FRONTEND_ORIGIN}/join?token={token}"


@router.get("/members")
async def list_members(user=Depends(get_current_user), db=Depends(get_db)):
    """Everyone on this project. Members see the roster; owners also get the
    pending invite links so they can pass one along by hand."""
    workspace, role = await require_workspace(user, db)
    is_owner = role in {"owner", "admin"}

    members = [m async for m in db.members.find({"workspace_id": workspace["_id"]})]
    user_ids = [m["user_id"] for m in members]
    users = {u["_id"]: u async for u in db.users.find({"_id": {"$in": user_ids}})}

    pending = {}
    if is_owner:
        async for inv in db.invites.find(
            {"workspace_id": workspace["_id"], "accepted_at": None}
        ):
            if inv.get("user_id"):
                pending[inv["user_id"]] = _invite_url(inv["token"])

    out = [
        serialize_member(m, users.get(m["user_id"]), pending.get(m["user_id"]))
        for m in members
    ]
    out.sort(key=lambda m: (m["role"] != "owner", m.get("email") or ""))
    return {"members": out, "can_manage": is_owner}


@router.post("/members", status_code=status.HTTP_201_CREATED)
async def add_members(
    body: AddMembersIn,
    request: Request,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Add people to the project by email address.

    Each address gets a placeholder account with no password and a single-use
    link. They choose their own password when they arrive — a password is never
    put in an email.
    """
    workspace = await require_owner(user, db, "add team members")
    now = datetime.now(timezone.utc)
    inviter = user.get("name") or user["email"]
    results = []
    brief_for: list[str] = []

    for raw in body.emails:
        email = str(raw).lower().strip()

        if email == user["email"].lower():
            results.append({"email": email, "status": "skipped",
                            "detail": "That's you — you already own this project."})
            continue

        existing_user = await db.users.find_one({"email": email})

        if existing_user:
            already = await db.members.find_one({"user_id": existing_user["_id"]})
            if already and already["workspace_id"] == workspace["_id"]:
                results.append({"email": email, "status": "skipped",
                                "detail": "Already on this project."})
                continue
            if already:
                results.append({"email": email, "status": "skipped",
                                "detail": "This person already belongs to another project."})
                continue
            member_user = existing_user
            needs_password = not existing_user.get("password_hash")
        else:
            member_user = {
                "_id": uuid.uuid4().hex,
                "email": email,
                "name": email.split("@")[0],
                "password_hash": None,      # they set it from the invite link
                "google_sub": None,
                "picture": None,
                "role": "member",
                "status": "invited",
                "created_at": now,
            }
            await db.users.insert_one(member_user)
            needs_password = True

        await db.members.insert_one(
            member_doc(workspace["_id"], member_user["_id"], "member",
                       invited_by=user["id"], status="invited")
        )

        token = secrets.token_urlsafe(24)
        await db.invites.insert_one({
            "_id": uuid4().hex,
            "workspace_id": workspace["_id"],
            "email": email,
            "user_id": member_user["_id"],
            "token": token,
            "invite_url": _invite_url(token),
            "needs_password": needs_password,
            "created_by": user["id"],
            "created_at": now,
            "expires_at": now + timedelta(days=INVITE_TTL_DAYS),
            "accepted_at": None,
        })

        # Queued rather than dispatched — see below.
        brief_for.append(member_user["_id"])

        emailed = await mailer.send_invite(email, workspace["name"], inviter, _invite_url(token))
        results.append({
            "email": email,
            "status": "invited",
            "emailed": emailed,
            "invite_url": _invite_url(token),
        })

    # Nobody asked for this. Adding people is the event; the agent goes and
    # researches the project for them so their briefs are waiting.
    #
    # One task for the whole batch, not one per person. The project research is
    # cached and shared, but tasks dispatched together all miss the cache — each
    # starts before any has written it — so five new teammates meant five
    # identical research runs competing for the same rate limit. Sequential
    # means the first fills the cache and the rest compose from it.
    if brief_for:
        background_tasks.add_task(
            _write_briefs,
            request.app.state.mongo_db,
            request.app.state.chroma_client,
            workspace["_id"],
            brief_for,
        )

    return {"results": results, "email_configured": mailer.is_configured()}


async def _write_briefs(db, chroma_client, workspace_id: str, user_ids: list[str]) -> None:
    """Brief each new teammate in turn, so they share one research pass."""
    for user_id in user_ids:
        try:
            await generate_brief(db, chroma_client, workspace_id, user_id)
        except Exception as exc:
            print(f"[brief] {user_id} failed: {exc}")


@router.delete("/members/{user_id}", status_code=204)
async def remove_member(
    user_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Revoke someone's access. Their pending invites die with it."""
    workspace = await require_owner(user, db, "remove team members")
    member = await db.members.find_one({"user_id": user_id, "workspace_id": workspace["_id"]})
    if not member:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not on this project")
    if member.get("role") in {"owner", "admin"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The project owner cannot be removed")

    await db.members.delete_one({"_id": member["_id"]})
    await db.invites.delete_many({"workspace_id": workspace["_id"], "user_id": user_id,
                                  "accepted_at": None})
