def _iso(val) -> str | None:
    """
    ISO-8601 with an explicit zone. Mongo hands datetimes back naive, in UTC;
    serialised bare, a browser reads them as local time and "just now" becomes
    "5 hours ago" in Hyderabad.
    """
    if val is None:
        return None
    if not hasattr(val, "isoformat"):
        return val
    if getattr(val, "tzinfo", None) is None:
        return val.isoformat() + "Z"
    return val.isoformat()


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
        # null = every source. A list narrows what they are answered from.
        "source_access": doc.get("source_access"),
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
        # Set when the watcher sees the project move under a brief written
        # against how it used to be.
        "stale_reason": doc.get("stale_reason"),
        # The last refresh failed but the brief shown is still the last good one.
        "refresh_error": doc.get("refresh_error"),
        "stale_at": _iso(doc.get("stale_at")),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
    }


def serialize_gap_report(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "workspace_id": doc["workspace_id"],
        "status": doc.get("status", "scanning"),
        "summary": doc.get("summary"),
        "gaps": doc.get("gaps", []),
        "error_message": doc.get("error_message"),
        "refresh_error": doc.get("refresh_error"),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
    }


def serialize_draft(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "gap_id": doc["gap_id"],
        "gap_title": doc.get("gap_title"),
        "status": doc.get("status", "drafting"),
        "draft": doc.get("draft"),
        "error_message": doc.get("error_message"),
        "updated_at": _iso(doc.get("updated_at")),
    }


def serialize_unanswered(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "question": doc.get("question"),
        "asked_by_name": doc.get("asked_by_name"),
        "times_asked": doc.get("times_asked", 1),
        "status": doc.get("status", "open"),
        "answer": doc.get("answer"),
        "answered_by": doc.get("answered_by"),
        "answered_at": _iso(doc.get("answered_at")),
        "created_at": _iso(doc.get("created_at")),
        "last_asked_at": _iso(doc.get("last_asked_at")),
    }
