import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, EmailStr, Field

from auth.deps import get_current_user
from core.config import settings
from core.security import create_jwt, hash_password, verify_password
from db.database import get_db
from db.models import serialize_user

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "access_token"


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
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
    if await db.users.find_one({"email": email}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    doc = {
        "_id": uuid.uuid4().hex,
        "email": email,
        "name": body.name.strip(),
        "password_hash": hash_password(body.password),
        "google_sub": None,
        "picture": None,
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
