def _iso(val) -> str | None:
    if val is None:
        return None
    return val.isoformat() if hasattr(val, "isoformat") else val


def serialize_user(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "email": doc["email"],
        "name": doc.get("name") or doc["email"].split("@")[0],
        "picture": doc.get("picture"),
        "has_password": bool(doc.get("password_hash")),
        "created_at": _iso(doc.get("created_at")),
    }


def serialize_workspace(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "owner_id": doc["owner_id"],
        "name": doc["name"],
        "description": doc.get("description", ""),
        "created_at": _iso(doc.get("created_at")),
    }


def serialize_source(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "workspace_id": doc["workspace_id"],
        "type": doc["type"],
        "label": doc.get("label", ""),
        "config": doc.get("config", {}),
        "status": doc.get("status", "pending"),
        "stats": doc.get("stats", {}),
        "error_message": doc.get("error_message"),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
    }


def serialize_invite(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "workspace_id": doc["workspace_id"],
        "token": doc["token"],
        "invite_url": doc["invite_url"],
        "created_at": _iso(doc.get("created_at")),
        "expires_at": _iso(doc.get("expires_at")),
    }


def serialize_chat_session(doc: dict, include_messages: bool = False) -> dict:
    out = {
        "id": doc["_id"],
        "workspace_id": doc["workspace_id"],
        "title": doc.get("title", "New chat"),
        "message_count": len(doc.get("messages", [])),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
    }
    if include_messages:
        out["messages"] = doc.get("messages", [])
    return out
