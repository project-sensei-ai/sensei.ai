from fastapi import Cookie, Depends, HTTPException, status
from jwt import InvalidTokenError

from core.security import decode_jwt
from db.database import get_db
from db.models import serialize_user


async def get_current_user(
    access_token: str | None = Cookie(None, alias="access_token"),
    db=Depends(get_db),
) -> dict:
    if not access_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_jwt(access_token)
    except InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")

    user = await db.users.find_one({"_id": payload.get("sub")})
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return serialize_user(user)
