"""
"Connect with Atlassian" — OAuth for tool grants, with nothing to paste.

Remote MCP servers from Atlassian, Notion, Linear, Sentry and others speak
MCP's OAuth 2.1 profile: the client discovers the authorization server,
registers itself dynamically, sends the person to log in, and receives tokens
it can refresh. So an owner can hand the agent an account the way they would
add an app to their phone — a login screen, a consent screen, done — without
Sensei holding a vendor-specific client secret for each service.

How the pieces fit:

    POST /api/tools/oauth/start     creates the grant (status: authorizing) and
                                    starts the connect in a worker thread
    the worker's redirect_handler   parks the login URL where the route can
                                    return it; the UI opens it in a popup
    GET  …/oauth/callback/{id}      the vendor sends the code here; it is
                                    handed to the waiting worker
    the worker                      exchanges the code, lists the tools,
                                    marks the grant connected

Tokens are stored encrypted on the grant and refreshed by the same provider on
later turns, where no redirect is possible: if a refresh fails the grant is
marked as needing the owner again, rather than failing quietly in chat.
"""
import asyncio
import json
import threading
import time
from datetime import datetime, timezone
from typing import Any

from core import secrets
from core.config import settings

# grant_id -> the handshake in flight
_PENDING: dict[str, dict[str, Any]] = {}
_MONGO = None


def _sync_db():
    """A blocking client for use from the MCP client's own thread — motor is
    bound to the request loop and cannot be used there."""
    global _MONGO
    if _MONGO is None:
        from pymongo import MongoClient
        _MONGO = MongoClient(settings.MONGO_DB)
    return _MONGO[settings.MONGO_DB_NAME]


def redirect_uri(grant_id: str) -> str:
    return f"{settings.FRONTEND_ORIGIN.rstrip('/')}/api/tools/oauth/callback/{grant_id}"


class GrantTokenStorage:
    """TokenStorage over the grant document. Reads come from memory (loaded
    once); writes go to memory and, encrypted, to Mongo."""

    def __init__(self, grant_id: str, stored: dict | None = None, defer_writes: bool = False):
        from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
        self.grant_id = grant_id
        self._tokens = None
        self._client_info = None
        # During the interactive handshake every write goes to memory and is
        # flushed once at the end: a database round-trip in the middle of the
        # flow delayed the login URL past the request's patience.
        self.defer_writes = defer_writes
        self.dirty = False
        stored = stored or {}
        if stored.get("tokens"):
            try:
                self._tokens = OAuthToken.model_validate(json.loads(secrets.decrypt(stored["tokens"])))
            except Exception:
                self._tokens = None
        if stored.get("client_info"):
            try:
                self._client_info = OAuthClientInformationFull.model_validate(stored["client_info"])
            except Exception:
                self._client_info = None

    async def get_tokens(self):
        return self._tokens

    async def set_tokens(self, tokens) -> None:
        self._tokens = tokens
        self.dirty = True
        if self.defer_writes:
            return
        payload = secrets.encrypt(tokens.model_dump_json())
        await asyncio.to_thread(
            lambda: _sync_db().tool_grants.update_one(
                {"_id": self.grant_id},
                {"$set": {"oauth.tokens": payload, "oauth.token_updated_at": datetime.now(timezone.utc),
                          "oauth.needs_reauth": False}},
            )
        )

    async def get_client_info(self):
        return self._client_info

    async def set_client_info(self, client_info) -> None:
        self._client_info = client_info
        self.dirty = True
        if self.defer_writes:
            return
        await asyncio.to_thread(
            lambda: _sync_db().tool_grants.update_one(
                {"_id": self.grant_id},
                {"$set": {"oauth.client_info": json.loads(client_info.model_dump_json())}},
            )
        )


    def flush(self) -> None:
        """Persist what the handshake produced, in one write."""
        update = {}
        if self._tokens is not None:
            update["oauth.tokens"] = secrets.encrypt(self._tokens.model_dump_json())
            update["oauth.token_updated_at"] = datetime.now(timezone.utc)
            update["oauth.needs_reauth"] = False
        if self._client_info is not None:
            update["oauth.client_info"] = json.loads(self._client_info.model_dump_json())
        if update:
            _sync_db().tool_grants.update_one({"_id": self.grant_id}, {"$set": update})
        self.dirty = False


def _client_metadata(grant_id: str, name: str):
    from mcp.shared.auth import OAuthClientMetadata
    return OAuthClientMetadata(
        client_name=f"Sensei — {name}",
        redirect_uris=[redirect_uri(grant_id)],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",
    )


def make_provider(grant: dict, interactive: bool):
    """The httpx auth for this grant. Interactive providers can send a person
    to log in; the ones used on ordinary turns cannot, and say so."""
    from mcp.client.auth import OAuthClientProvider

    grant_id = grant["_id"]
    storage = GrantTokenStorage(grant_id, grant.get("oauth"), defer_writes=interactive)

    if interactive:
        pending = _PENDING.setdefault(grant_id, {
            "auth_url": None, "url_ready": threading.Event(),
            "code": None, "state": None, "code_ready": threading.Event(),
        })

        async def redirect_handler(url: str) -> None:
            pending["auth_url"] = url
            pending["url_ready"].set()
            print(f"[oauth] login URL ready for {grant.get('name')}")

        async def callback_handler() -> tuple[str, str | None]:
            ok = await asyncio.to_thread(pending["code_ready"].wait, 300)
            if not ok or not pending.get("code"):
                raise RuntimeError("Nobody completed the login within five minutes")
            return pending["code"], pending.get("state")
    else:
        async def redirect_handler(url: str) -> None:
            _sync_db().tool_grants.update_one({"_id": grant_id}, {"$set": {"oauth.needs_reauth": True}})
            raise RuntimeError(
                f"{grant.get('name')} needs the owner to sign in again — the connection's "
                "authorization has lapsed. Reconnect it under Tools."
            )

        async def callback_handler() -> tuple[str, str | None]:
            raise RuntimeError("no interactive login available on this turn")

    provider = OAuthClientProvider(
        server_url=grant["url"],
        client_metadata=_client_metadata(grant_id, grant.get("name", "connection")),
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
        timeout=320.0,
    )
    provider.sensei_storage = storage
    return provider


def transport_with_auth(grant: dict, auth):
    url = grant["url"]
    if url.rstrip("/").endswith("/sse") or grant.get("kind") == "mcp_sse":
        from mcp.client.sse import sse_client
        return lambda: sse_client(url, auth=auth)
    from mcp.client.streamable_http import streamablehttp_client
    return lambda: streamablehttp_client(url, auth=auth)


def wait_for_auth_url(grant_id: str, timeout: float = 30.0) -> str | None:
    pending = _PENDING.get(grant_id)
    if not pending:
        return None
    pending["url_ready"].wait(timeout)
    return pending.get("auth_url")


def deliver_code(grant_id: str, code: str, state: str | None) -> bool:
    pending = _PENDING.get(grant_id)
    if not pending:
        return False
    pending["code"], pending["state"] = code, state
    pending["code_ready"].set()
    return True


def connect_interactively(grant: dict) -> None:
    """
    Runs in a worker thread. Opens the MCP session with an interactive
    provider — which triggers the login flow — then lists the tools and
    finishes the grant. Every outcome is written to the grant document.
    """
    from strands.tools.mcp import MCPClient
    from toolgrants.registry import classify, slug

    db = _sync_db()
    grant_id = grant["_id"]
    try:
        provider = make_provider(grant, interactive=True)
        client = MCPClient(transport_with_auth(grant, provider), prefix=slug(grant.get("name", "")),
                           startup_timeout=330)
        with client:
            listed = client.list_tools_sync()
        provider.sensei_storage.flush()
        tools = []
        for t in listed:
            mcp_tool = getattr(t, "mcp_tool", None)
            raw = getattr(mcp_tool, "name", None) or t.tool_name
            tools.append({
                "name": t.tool_name, "server_name": raw,
                "description": (getattr(mcp_tool, "description", None) or "")[:300],
                "access": classify(raw, getattr(mcp_tool, "annotations", None)),
            })
        db.tool_grants.update_one(
            {"_id": grant_id},
            {"$set": {"tools": tools, "status": "connected", "error_message": None,
                      "oauth.connected_at": datetime.now(timezone.utc),
                      "updated_at": datetime.now(timezone.utc)}},
        )
        print(f"[oauth] {grant.get('name')} connected with {len(tools)} tools")
    except Exception as exc:
        from core.errors import humanise
        msg = humanise(exc)
        if "five minutes" in str(exc):
            msg = "The login was not completed. Try connecting again."
        db.tool_grants.update_one(
            {"_id": grant_id},
            {"$set": {"status": "error", "error_message": msg, "updated_at": datetime.now(timezone.utc)}},
        )
        print(f"[oauth] {grant.get('name')} failed: {exc.__class__.__name__}: {str(exc)[:200]}")
    finally:
        _PENDING.pop(grant_id, None)


def start_connect(grant: dict) -> None:
    # The handshake record exists before the worker does, so the route can
    # wait on it immediately instead of racing the thread's first lines.
    _PENDING[grant["_id"]] = {
        "auth_url": None, "url_ready": threading.Event(),
        "code": None, "state": None, "code_ready": threading.Event(),
    }
    threading.Thread(target=connect_interactively, args=(grant,), daemon=True,
                     name=f"oauth-{grant['_id'][:8]}").start()


# Servers that speak MCP with OAuth, so the owner logs in instead of pasting.
OAUTH_PRESETS = [
    {"id": "atlassian", "name": "Atlassian (Jira + Confluence)", "url": "https://mcp.atlassian.com/v1/mcp",
     "blurb": "Jira issues and Confluence pages, read and write, as the account that signs in."},
    {"id": "notion", "name": "Notion", "url": "https://mcp.notion.com/mcp",
     "blurb": "Pages and databases the signed-in workspace shares with the integration."},
    {"id": "linear", "name": "Linear", "url": "https://mcp.linear.app/mcp",
     "blurb": "Issues, projects and cycles."},
    {"id": "sentry", "name": "Sentry", "url": "https://mcp.sentry.dev/mcp",
     "blurb": "Errors, issues and releases."},
    {"id": "asana", "name": "Asana", "url": "https://mcp.asana.com/sse",
     "blurb": "Tasks and projects."},
    {"id": "intercom", "name": "Intercom", "url": "https://mcp.intercom.com/mcp",
     "blurb": "Conversations and contacts."},
]
