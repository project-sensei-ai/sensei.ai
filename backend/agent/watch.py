"""
Watching for change, and staying quiet about most of it.

Anything can post an update on a timer. The requirement is harder: notice that
something changed, decide whether it *matters*, and say nothing when it does
not. A watcher that reports every README typo gets muted, and a muted watcher is
worse than none because people stop looking.

So the decision is staged, and the cheap stages come first:

    1. re-fetch each source                        no model
    2. hash the documents, diff against last seen  no model
    3. nothing changed?  stop here — the common case, and it is free
    4. something changed → one model call: is this material, and to whom
    5. material → write a digest and mark affected briefs stale

Most runs end at step 3 having spent nothing.
"""
import hashlib
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from strands import Agent, ModelRetryStrategy

from agent.agent import _build_model
from core import secrets
from core.config import settings
from core.errors import humanise


class ChangeVerdict(BaseModel):
    """The judgement that decides whether anyone hears about this."""
    materially_changed: bool = Field(
        description="True only if someone working on this project would want to know"
    )
    headline: str = Field(description="One sentence. Empty if nothing material changed.")
    detail: str = Field(default="", description="2-3 sentences on what changed and why it matters")
    affects: list[str] = Field(
        default_factory=list,
        description="What this touches — 'deployment', 'architecture', 'ownership', and so on",
    )
    severity: Literal["notable", "minor"] = "minor"


_JUDGE = """You decide whether a change to a project's documentation is worth
interrupting someone for.

You are given what changed: which documents are new, edited or gone, and
excerpts from the new content.

Say it is material when a person working here would want to know — a component
added or removed, a process or owner changed, a deployment or architecture
decision, a document that contradicts what they were told before.

Say it is NOT material for typos, formatting, reordering, wording, small
additions that change no meaning, or churn in generated files.

Most changes are not material. An empty answer is the right answer far more
often than not, and reporting everything is the same as reporting nothing."""


def _fingerprint(docs: list[dict]) -> dict[str, str]:
    """A content hash per document, so a diff needs no model and no storage."""
    out = {}
    for d in docs:
        meta = d.get("metadata") or {}
        key = str(meta.get("title") or meta.get("path") or meta.get("url")
                  or meta.get("data_type") or "unknown")
        out[key] = hashlib.sha256((d.get("content") or "").encode()).hexdigest()[:16]
    return out


async def _record_check(db, source: dict, fingerprint: dict[str, str]) -> None:
    """Record which documents we last saw, so the next check can diff against it."""
    await db.sources.update_one(
        {"_id": source["_id"]},
        {"$set": {
            "content_fingerprint": fingerprint,
            "last_checked_at": datetime.now(timezone.utc),
        }},
    )


async def _fetch(source: dict) -> list[dict]:
    from agent.tools import fetch_confluence, fetch_github, fetch_urls, fetch_jira
    secret = secrets.decrypt_dict(source.get("config_secret"))
    cfg = source.get("config", {})
    if source["type"] == "github":
        return await fetch_github(repo=cfg["repo"], pat=secret.get("pat", ""))
    if source["type"] == "url":
        return await fetch_urls(urls=cfg.get("urls", []))
    if source["type"] == "confluence":
        return await fetch_confluence(
            base_url=cfg["base_url"], email=cfg["email"],
            api_token=secret.get("api_token", ""), space_key=cfg["space_key"],
        )
    if source["type"] == "jira":
        return await fetch_jira(
            base_url=cfg["base_url"], email=cfg["email"],
            api_token=secret.get("api_token", ""), project_key=cfg["project_key"],
        )
    return []          # uploaded files cannot change underneath us


async def check_source(db, chroma_client, source: dict) -> dict | None:
    """
    Re-read one source and report what moved. No model involved.

    The live re-read exists to refresh the index, not just to nag: when content
    moved, we rewrite that source's chunks from the freshly fetched docs first,
    so answers stop being stale — then decide whether anyone needs telling.

    Returns None when nothing changed, which is the usual outcome.
    """
    try:
        docs = await _fetch(source)
    except Exception as exc:
        print(f"[watch] {source.get('label')}: {humanise(exc)}")
        return None
    if not docs:
        return None

    now = _fingerprint(docs)
    before = source.get("content_fingerprint") or {}

    added = [k for k in now if k not in before]
    changed = [k for k in now if k in before and before[k] != now[k]]
    removed = [k for k in before if k not in now]

    if not before or not (added or changed or removed):
        await _record_check(db, source, now)
        return None

    try:
        from agent.ingest import write_source_docs
        await write_source_docs(db, chroma_client, source["_id"], docs)
    except Exception as exc:
        # Leave the fingerprint stale so the next cycle retries the re-index;
        # forgetting the change would hide it forever.
        print(f"[watch] re-index failed for {source.get('label')}: {humanise(exc)}")
        return None

    await _record_check(db, source, now)

    excerpts = []
    for d in docs:
        meta = d.get("metadata") or {}
        key = str(meta.get("title") or meta.get("path") or meta.get("url")
                  or meta.get("data_type") or "unknown")
        if key in added or key in changed:
            excerpts.append(f"### {key}\n{(d.get('content') or '')[:600]}")
        if len(excerpts) >= 6:
            break

    return {
        "source": source.get("label"),
        "added": added[:20],
        "changed": changed[:20],
        "removed": removed[:20],
        "excerpts": excerpts,
    }


async def judge(changes: list[dict]) -> ChangeVerdict:
    """One model call, reached only when something actually moved."""
    summary = []
    for c in changes:
        summary.append(
            f"## {c['source']}\n"
            f"new: {', '.join(c['added']) or 'none'}\n"
            f"edited: {', '.join(c['changed']) or 'none'}\n"
            f"gone: {', '.join(c['removed']) or 'none'}\n"
            + "\n".join(c["excerpts"])
        )
    agent = Agent(
        model=_build_model(background=True),
        system_prompt=_JUDGE,
        retry_strategy=ModelRetryStrategy(max_attempts=3, initial_delay=2, max_delay=8),
    )
    return await agent.structured_output_async(
        ChangeVerdict, "What changed:\n\n" + "\n\n".join(summary)
    )


async def watch_workspace(db, chroma_client, workspace_id: str) -> dict:
    """
    Check a project for change and decide whether anyone should hear about it.

    Returns what happened, so a manual run can say "nothing changed" rather than
    appearing to do nothing.
    """
    now = datetime.now(timezone.utc)
    changes = []
    async for source in db.sources.find({"workspace_id": workspace_id, "status": "ready"}):
        found = await check_source(db, chroma_client, source)
        if found:
            changes.append(found)

    if not changes:
        return {"checked": True, "changed": False, "material": False,
                "message": "Nothing has changed since the last check."}

    try:
        verdict = await judge(changes)
    except Exception as exc:
        return {"checked": True, "changed": True, "material": False,
                "message": humanise(exc)}

    if not verdict.materially_changed:
        # The silence condition. Something moved; nobody needs telling.
        print(f"[watch] {workspace_id}: changes found, none material")
        return {"checked": True, "changed": True, "material": False,
                "message": "Something changed, but nothing a person needs to act on."}

    await db.change_digests.insert_one({
        "_id": uuid4().hex,
        "workspace_id": workspace_id,
        "headline": verdict.headline,
        "detail": verdict.detail,
        "affects": verdict.affects,
        "severity": verdict.severity,
        "sources": [c["source"] for c in changes],
        "at": now,
        "acknowledged": False,
    })

    # Briefs were written against the project as it was. Say so rather than
    # letting someone act on a stale reading list.
    await db.briefs.update_many(
        {"workspace_id": workspace_id, "status": "ready"},
        {"$set": {"stale_reason": verdict.headline, "stale_at": now}},
    )
    # And the research behind them is out of date.
    await db.research_cache.delete_many({"workspace_id": workspace_id})

    print(f"[watch] {workspace_id}: {verdict.headline}")
    return {"checked": True, "changed": True, "material": True,
            "headline": verdict.headline, "detail": verdict.detail}
