"""Tool grants — connect an MCP server, decide what the agent may do with it."""
import asyncio
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from auth.deps import get_current_user
from core import secrets
from core.errors import humanise
from db.database import get_db
from db.membership import OWNER_ROLES, require_owner, require_workspace
from toolgrants import pool, registry

router = APIRouter(tags=["tools"])


class GrantIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    kind: Literal["mcp_http", "mcp_sse", "mcp_stdio"]
    url: str | None = None
    # e.g. "Bearer ghp_..." — stored encrypted, never returned.
    authorization: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    allow_write: bool = False

    @field_validator("url")
    @classmethod
    def _url(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("The server URL must start with http:// or https://")
        return v


class GrantPatch(BaseModel):
    allow_write: bool | None = None
    disabled_tools: list[str] | None = None
    name: str | None = Field(None, min_length=1, max_length=60)


def _check_shape(body: GrantIn) -> None:
    if body.kind in ("mcp_http", "mcp_sse") and not body.url:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A server URL is required")
    if body.kind == "mcp_stdio" and not body.command:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A command is required for a local server")


async def _probe_or_422(doc: dict, secret: dict) -> list[dict]:
    try:
        return await asyncio.wait_for(asyncio.to_thread(registry.probe, doc, secret), timeout=45)
    except asyncio.TimeoutError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The server did not answer within 45 seconds. Check the URL, and that it speaks MCP.",
        )
    except Exception as exc:
        text = str(exc)
        if "401" in text or "403" in text or "Unauthorized" in text:
            hint = "The server rejected the credential. Check the Authorization value."
        elif "404" in text:
            hint = "Nothing speaks MCP at that URL. Check the path — many servers use /mcp or /sse."
        else:
            hint = humanise(exc)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Could not connect: {hint}")


@router.post("", status_code=status.HTTP_201_CREATED)
async def connect_tool(body: GrantIn, user=Depends(get_current_user), db=Depends(get_db)):
    ws = await require_owner(user, db, "connect tools")
    _check_shape(body)

    secret: dict = {}
    if body.authorization:
        secret["authorization"] = body.authorization.strip()
    if body.env:
        secret["env"] = body.env

    now = datetime.now(timezone.utc)
    doc = {
        "_id": uuid4().hex,
        "workspace_id": ws["_id"],
        "name": body.name.strip(),
        "kind": body.kind,
        "url": body.url,
        "headers": body.headers,
        "command": body.command,
        "args": body.args,
        "allow_write": body.allow_write,
        "disabled_tools": [],
        "status": "connected",
        "created_at": now,
        "created_by": user["id"],
        "uses": 0,
    }
    # Connect now, so a broken grant never gets stored. The tool list it
    # returns is what the Trust page shows and what the write gate enforces.
    doc["tools"] = await _probe_or_422(doc, secret)
    if secret:
        doc["config_secret"] = secrets.encrypt_dict(
            {k: v for k, v in secret.items() if isinstance(v, str)}
        )
        if "env" in secret:
            doc["config_secret"]["env"] = {k: secrets.encrypt(v) for k, v in secret["env"].items()}

    await db.tool_grants.insert_one(doc)
    await pool.drop(ws["_id"])     # next turn opens a session that includes this
    return {"grant": registry.serialize_grant(doc, for_owner=True)}


@router.get("")
async def list_tools(user=Depends(get_current_user), db=Depends(get_db)):
    ws, role = await require_workspace(user, db)
    grants = await registry.load_grants(db, ws["_id"])
    is_owner = role in OWNER_ROLES
    return {
        "grants": [registry.serialize_grant(g, for_owner=is_owner) for g in grants],
        "can_manage": is_owner,
    }


@router.patch("/{grant_id}")
async def update_tool(grant_id: str, body: GrantPatch, user=Depends(get_current_user), db=Depends(get_db)):
    ws = await require_owner(user, db, "change what tools the agent may use")
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nothing to change")
    changes["updated_at"] = datetime.now(timezone.utc)
    result = await db.tool_grants.find_one_and_update(
        {"_id": grant_id, "workspace_id": ws["_id"]}, {"$set": changes}, return_document=True
    )
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such tool connection")
    return {"grant": registry.serialize_grant(result, for_owner=True)}


@router.post("/{grant_id}/test")
async def test_tool(grant_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Reconnect and refresh the tool list — servers add tools over time."""
    ws = await require_owner(user, db, "test tool connections")
    doc = await db.tool_grants.find_one({"_id": grant_id, "workspace_id": ws["_id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such tool connection")
    secret = secrets.decrypt_dict(doc.get("config_secret"))
    if isinstance(secret.get("env"), dict):
        secret["env"] = {k: secrets.decrypt(v) for k, v in secret["env"].items()}
    try:
        tools = await _probe_or_422(doc, secret)
        await db.tool_grants.update_one(
            {"_id": grant_id},
            {"$set": {"tools": tools, "status": "connected", "error_message": None,
                      "updated_at": datetime.now(timezone.utc)}},
        )
    except HTTPException as exc:
        await db.tool_grants.update_one(
            {"_id": grant_id},
            {"$set": {"status": "error", "error_message": exc.detail,
                      "updated_at": datetime.now(timezone.utc)}},
        )
        raise
    doc = await db.tool_grants.find_one({"_id": grant_id})
    return {"grant": registry.serialize_grant(doc, for_owner=True)}


@router.delete("/{grant_id}", status_code=204)
async def revoke_tool(grant_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    ws = await require_owner(user, db, "revoke tools")
    result = await db.tool_grants.delete_one({"_id": grant_id, "workspace_id": ws["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such tool connection")
    await pool.drop(ws["_id"])     # revocation takes effect on the next turn, not the next restart
