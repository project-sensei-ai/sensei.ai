def serialize_user(doc: dict) -> dict:
    created_at = doc.get("created_at")
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()
    return {
        "id": doc["_id"],
        "email": doc["email"],
        "name": doc.get("name") or doc["email"].split("@")[0],
        "picture": doc.get("picture"),
        "has_password": bool(doc.get("password_hash")),
        "created_at": created_at,
    }
