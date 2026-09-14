"""
Tool grants — the owner hands the agent a capability, not just a document.

A source is something the agent *reads* and indexes. A tool grant is something
it can *use*: a Model Context Protocol server the owner connects with a
credential — GitHub, Jira, Slack, Gmail through Zapier, an internal API — and
whose tools then appear inside the Strands agent loop as if they were native.

This is how a colleague gets onboarded in practice. Nobody hands a new hire a
zip of documents; they get accounts. The same shape applies here, with two
rules a human onboarding never manages to enforce:

  1. Every tool is classified read or write before the agent sees it, and
     write tools are refused unless the owner switched them on for this grant.
     The refusal happens inside the agent loop (a Strands hook cancels the
     call), so it holds even if the model decides otherwise.
  2. The Trust page lists every tool by name, with its class, next to the
     credential that unlocked it. What the agent could do is never a surprise.

Transport-agnostic: streamable HTTP, SSE, or a local stdio process.
"""
import re
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from typing import Any

from core import secrets
from db.models import _iso

KINDS = ("mcp_http", "mcp_sse", "mcp_stdio", "mcp_oauth")

# Names that almost always change state. MCP annotations win when a server
# provides them; this is the fallback for the many that do not.
_WRITE_HINT = re.compile(
    r"(create|update|delete|write|send|post|put|patch|remove|add|set|move|transition|"
    r"assign|upload|insert|edit|reply|publish|merge|close|archive|trash|push|comment|"
    r"resolve|submit|cancel|run|execute|trigger|dispatch|invite|share|rename|fork|"
    r"star|label|tag|approve|reject|schedule|book|pay|transfer|revoke|grant|enable|disable)",
    re.IGNORECASE,
)
_READ_HINT = re.compile(r"^(get|list|search|read|fetch|find|query|describe|show|lookup|view|check)", re.IGNORECASE)


def slug(name: str) -> str:
    """A prefix for tool names, so two servers' `search` tools do not collide."""
    s = re.sub(r"[^a-z0-9]+", "_", (name or "tool").lower()).strip("_")
    return s[:24] or "tool"


def classify(tool_name: str, annotations: Any = None) -> str:
    """'read' or 'write'. Annotations from the server are trusted first."""
    if annotations is not None:
        get = annotations.get if isinstance(annotations, dict) else lambda k, d=None: getattr(annotations, k, d)
        if get("readOnlyHint") is True:
            return "read"
        if get("destructiveHint") is True or get("readOnlyHint") is False:
            return "write"
    if _READ_HINT.match(tool_name):
        return "read"
    if _WRITE_HINT.search(tool_name):
        return "write"
    return "read"


def _headers(grant: dict, secret: dict) -> dict:
    headers = dict(grant.get("headers") or {})
    auth = (secret or {}).get("authorization")
    if auth:
        headers["Authorization"] = auth
    return headers


def make_transport(grant: dict, secret: dict):
    """A zero-arg callable that opens the MCP transport — what MCPClient wants."""
    kind = grant.get("kind")
    if kind == "mcp_oauth":
        # The credential is a token the person earned by logging in, refreshed
        # by the provider itself. No header to build.
        from toolgrants.oauth import make_provider, transport_with_auth
        return transport_with_auth(grant, make_provider(grant, interactive=False))
    if kind == "mcp_http":
        from mcp.client.streamable_http import streamablehttp_client
        url, headers = grant["url"], _headers(grant, secret)
        return lambda: streamablehttp_client(url, headers=headers)
    if kind == "mcp_sse":
        from mcp.client.sse import sse_client
        url, headers = grant["url"], _headers(grant, secret)
        return lambda: sse_client(url, headers=headers)
    if kind == "mcp_stdio":
        import os
        from mcp import StdioServerParameters, stdio_client
        env = {**os.environ, **(secret.get("env") or {})}
        params = StdioServerParameters(
            command=grant["command"], args=list(grant.get("args") or []), env=env
        )
        return lambda: stdio_client(params)
    raise ValueError(f"Unknown tool grant kind: {kind}")


def open_client(grant: dict, secret: dict | None = None):
    """An MCPClient for this grant. Caller must start()/stop() it, or use `with`."""
    from strands.tools.mcp import MCPClient
    secret = secret if secret is not None else secrets.decrypt_dict(grant.get("config_secret"))
    return MCPClient(
        make_transport(grant, secret),
        prefix=slug(grant.get("name", "")),
        startup_timeout=25,
    )


def probe(grant: dict, secret: dict) -> list[dict]:
    """
    Connect once, list the tools, disconnect. Runs at grant time so a bad URL or
    an expired token fails in the form, not silently in someone's chat later.
    """
    client = open_client(grant, secret)
    with client:
        tools = client.list_tools_sync()
    out = []
    for t in tools:
        mcp_tool = getattr(t, "mcp_tool", None)
        raw_name = getattr(mcp_tool, "name", None) or t.tool_name
        annotations = getattr(mcp_tool, "annotations", None)
        out.append({
            "name": t.tool_name,                     # prefixed — what the agent calls
            "server_name": raw_name,                 # what the server calls it
            "description": (getattr(mcp_tool, "description", None) or "")[:300],
            "access": classify(raw_name, annotations),
        })
    return out


def enabled_tool_names(grant: dict) -> set[str]:
    """Tools the agent may call under this grant, after the owner's choices."""
    names = set()
    for t in grant.get("tools") or []:
        if t.get("access") == "write" and not grant.get("allow_write"):
            continue
        if grant.get("disabled_tools") and t["name"] in grant["disabled_tools"]:
            continue
        names.add(t["name"])
    return names


class WriteGate:
    """
    A Strands hook: refuses tool calls the owner has not permitted.

    Installed on the agent rather than filtered out of the tool list on purpose.
    Leaving a write tool *visible* but refusing it means the agent can tell the
    person "I can see a create_issue tool but I am not allowed to use it — ask
    the owner", which is a far better answer than pretending the tool does not
    exist. The refusal message is what the model receives as the tool result.
    """

    def __init__(self, permitted: set[str], grant_names: dict[str, str], on_refusal=None):
        self.permitted = permitted
        self.grant_names = grant_names     # prefix -> grant display name
        self.on_refusal = on_refusal
        self.refusals: list[dict] = []

    def register_hooks(self, registry, **kwargs) -> None:
        from strands.hooks import BeforeToolCallEvent
        registry.add_callback(BeforeToolCallEvent, self._before)

    def _before(self, event) -> None:
        name = (event.tool_use or {}).get("name", "")
        prefix = name.split("_", 1)[0]
        if prefix not in self.grant_names:
            return  # a built-in tool, not one that came through a grant
        if name in self.permitted:
            return
        grant = self.grant_names.get(prefix, "this connection")
        msg = (
            f"Refused: `{name}` changes state in {grant}, and the project owner has "
            "not allowed write actions on that connection. Tell the person exactly "
            "this, and that the owner can enable it under Tools."
        )
        self.refusals.append({"tool": name, "grant": grant})
        event.cancel_tool = msg
        if self.on_refusal:
            self.on_refusal(name, grant)


# A tool description from a big server can run to a thousand characters; forty
# of them is more schema than question. Enough to choose by, no more.
MAX_DESCRIPTION = 220


def _trim(tool) -> None:
    mcp_tool = getattr(tool, "mcp_tool", None)
    desc = getattr(mcp_tool, "description", None)
    if mcp_tool is not None and desc and len(desc) > MAX_DESCRIPTION:
        try:
            mcp_tool.description = desc[:MAX_DESCRIPTION].rsplit(" ", 1)[0] + "…"
        except Exception:
            pass


_WORD = re.compile(r"[a-z0-9]{3,}")
# Words every question and every tool description share. Counting them made
# "which Confluence pages cover deployment" pick eight GitHub tools.
_FILLER = {
    "the", "and", "for", "with", "what", "which", "who", "whom", "when", "where", "why", "how",
    "have", "has", "had", "are", "was", "were", "our", "your", "you", "this", "that", "these",
    "those", "from", "into", "about", "does", "did", "can", "could", "would", "should", "will",
    "there", "their", "them", "they", "its", "any", "all", "not", "but", "get", "got", "use",
    "using", "please", "tell", "give", "also", "just", "like", "need", "want", "know", "some",
    "more", "most", "than", "then", "each", "other", "only", "been", "being", "here", "such",
}


def select_relevant(tools: list, question: str, limit: int, always: set[str] | None = None) -> list:
    """
    The handful of granted tools this question plausibly needs.

    A colleague with fifty apps does not open all fifty to answer one question.
    Sending every tool's schema on every call also costs more tokens than the
    question itself and trips provider limits. So: score each tool by lexical
    overlap between the question and the tool's name and description, keep the
    top `limit`, and always keep the generic entry points (search, list, get).
    """
    if len(tools) <= limit:
        return tools
    q = set(_WORD.findall((question or "").lower())) - _FILLER
    always = always or set()

    def score(t) -> float:
        name = t.tool_name.lower()
        desc = (getattr(getattr(t, "mcp_tool", None), "description", "") or "").lower()
        words = set(_WORD.findall(name.replace("_", " "))) | set(_WORD.findall(desc[:400]))
        overlap = len(q & words)
        base = 0.5 if any(k in name for k in ("search", "list", "get_me", "get_repo", "get_issue", "get_pull")) else 0.0
        return overlap + base

    # Only tools the question actually touches. A documentation question
    # should not pay for fifty GitHub schemas it will never call.
    ranked = sorted((t for t in tools if score(t) >= 1), key=score, reverse=True)
    keep = [t for t in tools if t.tool_name in always]
    for t in ranked:
        if len(keep) >= limit:
            break
        if t not in keep:
            keep.append(t)
    return keep


class GrantSession:
    """
    Everything a running agent needs from the workspace's grants, opened
    together and closed together.
    """

    def __init__(self):
        self.clients: list = []
        self.tools: list = []
        self.permitted: set[str] = set()
        self.grant_names: dict[str, str] = {}
        self.narration: dict[str, str] = {}
        self.failed: list[dict] = []

    def open(self, grants: list[dict]) -> "GrantSession":
        for g in grants:
            # A sign-in that never finished, or a connection already known to
            # be broken, is skipped rather than retried on every question.
            if g.get("status", "connected") != "connected":
                continue
            prefix = slug(g.get("name", ""))
            self.grant_names[prefix] = g.get("name", prefix)
            try:
                client = open_client(g)
                client.start()
                self.clients.append(client)
                listed = client.list_tools_sync()
            except Exception as exc:
                # One dead server must not take the whole colleague down.
                self.failed.append({"grant": g.get("name"), "error": str(exc)[:200]})
                continue
            enabled = enabled_tool_names(g)
            known = {t["name"]: t for t in (g.get("tools") or [])}
            for t in listed:
                _trim(t)
                self.tools.append(t)
                spec = known.get(t.tool_name)
                access = spec["access"] if spec else classify(t.tool_name.split("_", 1)[-1])
                # A tool the server added since the grant was probed is treated
                # by class: reads allowed, writes only if the owner said so.
                if t.tool_name in enabled or (not spec and (access == "read" or g.get("allow_write"))):
                    self.permitted.add(t.tool_name)
                verb = t.tool_name[len(prefix) + 1:].replace("_", " ") if t.tool_name.startswith(prefix + "_") else t.tool_name
                self.narration[t.tool_name] = f"Using {g.get('name')}: {verb}"
        return self

    def close(self) -> None:
        for c in self.clients:
            try:
                c.stop(None, None, None)
            except Exception:
                pass
        self.clients.clear()

    def gate(self, on_refusal=None) -> WriteGate:
        return WriteGate(self.permitted, self.grant_names, on_refusal)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def serialize_grant(doc: dict, for_owner: bool = False) -> dict:
    tools = doc.get("tools") or []
    out = {
        "id": doc["_id"],
        "workspace_id": doc["workspace_id"],
        "name": doc.get("name"),
        "kind": doc.get("kind"),
        "url": doc.get("url"),
        "command": doc.get("command"),
        "args": doc.get("args") or [],
        "allow_write": bool(doc.get("allow_write")),
        "disabled_tools": doc.get("disabled_tools") or [],
        "tools": tools,
        "read_count": sum(1 for t in tools if t.get("access") == "read"),
        "write_count": sum(1 for t in tools if t.get("access") == "write"),
        "status": doc.get("status", "connected"),
        "error_message": doc.get("error_message"),
        "auth": "oauth" if doc.get("kind") == "mcp_oauth" else "token",
        "needs_reauth": bool((doc.get("oauth") or {}).get("needs_reauth")),
        "created_at": _iso(doc.get("created_at")),
        "last_used_at": _iso(doc.get("last_used_at")),
        "uses": doc.get("uses", 0),
    }
    if for_owner:
        if doc.get("kind") == "mcp_oauth":
            tokens = (doc.get("oauth") or {}).get("tokens")
            out["credential_state"] = "encrypted" if isinstance(tokens, str) and tokens.startswith("enc:") else ("plaintext" if tokens else "none")
            out["has_credential"] = bool(tokens)
        else:
            out["credential_state"] = secrets.status(doc.get("config_secret"))
            out["has_credential"] = bool(doc.get("config_secret"))
    return out


async def load_grants(db, workspace_id: str) -> list[dict]:
    return [g async for g in db.tool_grants.find({"workspace_id": workspace_id}).sort("created_at", 1)]


async def touch(db, workspace_id: str, tool_name: str) -> None:
    """Record a use, so the Trust page can say when each grant was last exercised."""
    prefix = tool_name.split("_", 1)[0]
    try:
        async for g in db.tool_grants.find({"workspace_id": workspace_id}):
            if slug(g.get("name", "")) == prefix:
                await db.tool_grants.update_one(
                    {"_id": g["_id"]},
                    {"$set": {"last_used_at": datetime.now(timezone.utc)}, "$inc": {"uses": 1}},
                )
                break
    except Exception:
        pass
