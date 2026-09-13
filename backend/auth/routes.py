import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, EmailStr, Field

from auth.deps import get_current_user
from core.config import settings
from core.security import create_jwt, hash_password, verify_password
from db.database import get_db
from db.membership import member_doc
from db.models import serialize_user

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "access_token"


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["owner", "member"] = "owner"


class AcceptInviteIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    name: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthIn(BaseModel):
    credential: str


class SetPasswordIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    current_password: str | None = Field(default=None, max_length=128)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
        max_age=settings.JWT_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, response: Response, db=Depends(get_db)):
    email = body.email.lower()

    # Team members never self-register. A project owner puts their address on the
    # allowlist first, and they arrive through the link that generates. Without
    # that, anyone could create an account and go looking for a project to join.
    if body.role == "member":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Team members join by invitation. Ask your project owner to add your "
            "email — you'll get a link to set your password.",
        )

    existing = await db.users.find_one({"email": email})
    if existing and existing.get("status") == "invited":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You've already been added to a project. Open the invite link sent to "
            "this address to set your password.",
        )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    doc = {
        "_id": uuid.uuid4().hex,
        "email": email,
        "name": body.name.strip(),
        "password_hash": hash_password(body.password),
        "google_sub": None,
        "picture": None,
        "role": "owner",
        "status": "active",
        "created_at": datetime.now(timezone.utc),
    }
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    _set_session_cookie(response, create_jwt(doc["_id"], email))
    return {"user": serialize_user(doc)}


@router.post("/login")
async def login(body: LoginIn, response: Response, db=Depends(get_db)):
    user = await db.users.find_one({"email": body.email.lower()})
    if user and user.get("status") == "invited":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You have an invite waiting. Open the link sent to this address to set "
            "your password, then log in.",
        )
    if user and not user.get("password_hash"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This account uses Google sign-in. Use 'Continue with Google' below.",
        )
    if not user or not verify_password(body.password, user.get("password_hash")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    _set_session_cookie(response, create_jwt(user["_id"], user["email"]))
    return {"user": serialize_user(user)}


@router.post("/google")
async def google_auth(body: GoogleAuthIn, response: Response, db=Depends(get_db)):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Google sign-in is not configured",
        )

    try:
        info = id_token.verify_oauth2_token(
            body.credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Google credential")

    if not info.get("email_verified"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Google account email not verified")

    google_sub = info["sub"]
    email = info["email"].lower()

    user = await db.users.find_one({"google_sub": google_sub})
    if not user:
        existing_by_email = await db.users.find_one({"email": email})
        if existing_by_email and not existing_by_email.get("google_sub"):
            # Link the existing password account to this Google identity.
            await db.users.update_one(
                {"_id": existing_by_email["_id"]}, {"$set": {"google_sub": google_sub}}
            )
            user = {**existing_by_email, "google_sub": google_sub}
        elif existing_by_email:
            user = existing_by_email

    if not user:
        user = {
            "_id": uuid.uuid4().hex,
            "email": email,
            "name": info.get("name") or email.split("@")[0],
            "picture": info.get("picture"),
            "password_hash": None,
            "google_sub": google_sub,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            await db.users.insert_one(user)
        except DuplicateKeyError:
            user = await db.users.find_one({"email": email}) or user

    _set_session_cookie(response, create_jwt(user["_id"], user["email"]))
    return {"user": serialize_user(user)}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": user}


@router.post("/set-password")
async def set_password(
    body: SetPasswordIn, user: dict = Depends(get_current_user), db=Depends(get_db)
):
    doc = await db.users.find_one({"_id": user["id"]})
    if doc and doc.get("password_hash"):
        # Changing an existing password requires proving the current one.
        if not body.current_password or not verify_password(
            body.current_password, doc["password_hash"]
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Current password is incorrect"
            )
        message = "Password updated"
    else:
        message = "Password set — you can now log in with email too"

    await db.users.update_one(
        {"_id": user["id"]}, {"$set": {"password_hash": hash_password(body.password)}}
    )
    return {"message": message}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"message": "Logged out"}


# ── Invitations ───────────────────────────────────────────────────────────────

@router.get("/invite/{token}")
async def inspect_invite(token: str, db=Depends(get_db)):
    """
    Public: describe an invite so its landing page can render before anyone signs
    in. Deliberately thin — the address it was issued to, the project name, and
    whether a password still needs setting. Nothing about the project's contents.
    """
    invite = await db.invites.find_one({"token": token})
    if not invite:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This invite link is not valid")

    expires_at = invite.get("expires_at")
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status.HTTP_410_GONE, "This invite link has expired")

    if invite.get("accepted_at"):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This invite has already been used. Log in instead.")

    workspace = await db.workspaces.find_one({"_id": invite["workspace_id"]})
    inviter = await db.users.find_one({"_id": invite.get("created_by")})
    member_user = await db.users.find_one({"_id": invite.get("user_id")})

    return {
        "email": invite["email"],
        "workspace_name": workspace["name"] if workspace else "a project",
        "invited_by": (inviter or {}).get("name") or (inviter or {}).get("email"),
        "needs_password": not (member_user or {}).get("password_hash"),
    }


@router.post("/accept-invite")
async def accept_invite(body: AcceptInviteIn, response: Response, db=Depends(get_db)):
    """Set a password against a single-use invite token and activate the account."""
    invite = await db.invites.find_one({"token": body.token})
    if not invite:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This invite link is not valid")
    if invite.get("accepted_at"):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This invite has already been used. Log in instead.")

    expires_at = invite.get("expires_at")
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status.HTTP_410_GONE, "This invite link has expired")

    user = await db.users.find_one({"_id": invite["user_id"]})
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That account no longer exists")

    now = datetime.now(timezone.utc)
    updates = {"password_hash": hash_password(body.password), "status": "active"}
    if body.name and body.name.strip():
        updates["name"] = body.name.strip()
    await db.users.update_one({"_id": user["_id"]}, {"$set": updates})

    # Activate the membership the owner created when they added this address.
    result = await db.members.update_one(
        {"user_id": user["_id"], "workspace_id": invite["workspace_id"]},
        {"$set": {"status": "active", "joined_at": now}},
    )
    if result.matched_count == 0:
        await db.members.insert_one(
            member_doc(invite["workspace_id"], user["_id"], "member",
                       invited_by=invite.get("created_by"), status="active")
        )

    await db.invites.update_one({"_id": invite["_id"]}, {"$set": {"accepted_at": now}})

    _set_session_cookie(response, create_jwt(user["_id"], user["email"]))
    return {"user": serialize_user({**user, **updates})}
