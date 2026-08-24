from fastapi import HTTPException, Request, status


def get_db(request: Request):
    db = getattr(request.app.state, "mongo_db", None)
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return db


async def ensure_indexes(db) -> None:
    # Drop legacy sparse-unique index if present (nulls collided on it).
    try:
        await db.users.drop_index("google_sub_1")
    except Exception:
        pass
    await db.users.create_index("email", unique=True)
    # Unique only for actual Google IDs; explicit nulls must not collide.
    try:
        await db.users.create_index(
            "google_sub",
            unique=True,
            partialFilterExpression={"google_sub": {"$type": "string"}},
        )
    except Exception as exc:
        print(f"[DB] index warning: {exc}")
