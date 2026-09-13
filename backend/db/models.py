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
        "role": doc.get("role", "owner"),
        "status": doc.get("status", "active"),
        "created_at": _iso(doc.get("created_at")),
    }


def serialize_workspace(doc: dict, role: str | None = None) -> dict:
    out = {
        "id": doc["_id"],
        "owner_id": doc["owner_id"],
        "name": doc["name"],
        "description": doc.get("description", ""),
        "created_at": _iso(doc.get("created_at")),
    }
    if role is not None:
        out["role"] = role
    return out


def serialize_member(doc: dict, user: dict | None = None, invite_url: str | None = None) -> dict:
    out = {
        "id": doc["_id"],
        "workspace_id": doc["workspace_id"],
        "user_id": doc["user_id"],
        "role": doc.get("role", "member"),
        "status": doc.get("status", "active"),
        "invited_at": _iso(doc.get("invited_at")),
        "joined_at": _iso(doc.get("joined_at")),
    }
    if user:
        out["email"] = user.get("email")
        out["name"] = user.get("name") or (user.get("email") or "").split("@")[0]
        out["picture"] = user.get("picture")
    if invite_url:
        # Surfaced so an owner can hand the link over directly when mail is not
        # configured — which is how reviewers exercise the flow.
        out["invite_url"] = invite_url
    return out


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


def serialize_brief(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "workspace_id": doc["workspace_id"],
        "user_id": doc["user_id"],
        "person_name": doc.get("person_name"),
        "person_email": doc.get("person_email"),
        "status": doc.get("status", "generating"),
        "brief": doc.get("brief"),
        "error_message": doc.get("error_message"),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
    }
