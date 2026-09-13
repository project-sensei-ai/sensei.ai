"""
Open MCP sessions, kept warm.

Connecting to a tool server costs several seconds — the GitHub one lists its
forty-seven tools in about five — and a colleague who reconnected to every
system before answering each question would be a slow colleague. So one
session per workspace stays open across turns, and is only rebuilt when the
grants change (a new connection, a write switch flipped, a tool disabled) or
when it has been open long enough that a server-side session may have lapsed.

Also the fix for a subtler problem: closing an MCP client joins a background
thread, and doing that inside a request handler stalls the event loop for
everyone. Sessions here are closed off the loop, and only at shutdown or on
rebuild.
"""
import asyncio
import hashlib
import json
import time

from toolgrants.registry import GrantSession

_POOL: dict[str, tuple[str, float, GrantSession]] = {}   # workspace -> (fingerprint, opened_at, session)
_LOCK = asyncio.Lock()
MAX_AGE = 15 * 60


def _fingerprint(grants: list[dict]) -> str:
    key = [
        (g["_id"], str(g.get("updated_at") or g.get("created_at")), bool(g.get("allow_write")),
         sorted(g.get("disabled_tools") or []), g.get("status"))
        for g in grants
    ]
    return hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()


async def get_session(workspace_id: str, grants: list[dict]) -> GrantSession | None:
    """A warm session for these grants, opened off the event loop if needed."""
    if not grants:
        await drop(workspace_id)
        return None
    fp = _fingerprint(grants)
    async with _LOCK:
        cached = _POOL.get(workspace_id)
        if cached and cached[0] == fp and (time.time() - cached[1]) < MAX_AGE:
            return cached[2]
        if cached:
            await asyncio.to_thread(cached[2].close)
            _POOL.pop(workspace_id, None)
        session = await asyncio.to_thread(lambda: GrantSession().open(grants))
        _POOL[workspace_id] = (fp, time.time(), session)
        return session


async def drop(workspace_id: str) -> None:
    async with _LOCK:
        cached = _POOL.pop(workspace_id, None)
    if cached:
        await asyncio.to_thread(cached[2].close)


async def close_all() -> None:
    items = list(_POOL.values())
    _POOL.clear()
    for _, _, session in items:
        try:
            await asyncio.wait_for(asyncio.to_thread(session.close), timeout=5)
        except Exception:
            pass


def stats() -> dict:
    return {ws: {"tools": len(s.tools), "age_s": int(time.time() - t)} for ws, (_, t, s) in _POOL.items()}
