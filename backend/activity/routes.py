"""
What the agent has been doing.

Most of this product's work happens when nobody is looking — a brief written
because someone was added, an audit run because a source landed. Without a feed
that is invisible, and invisible autonomy is indistinguishable from none.

Assembled from records the work already leaves behind. Nothing new is written
just to populate a timeline.
"""
from fastapi import APIRouter, Depends

from auth.deps import get_current_user
from db.database import get_db
from db.membership import OWNER_ROLES, require_workspace
from db.models import _iso

router = APIRouter(tags=["activity"])


@router.get("")
async def feed(limit: int = 30, user=Depends(get_current_user), db=Depends(get_db)):
    workspace, role = await require_workspace(user, db)
    ws = workspace["_id"]
    is_owner = role in OWNER_ROLES
    events: list[dict] = []

    def add(at, kind, title, detail, unprompted):
        if at:
            events.append({"at": _iso(at), "kind": kind, "title": title,
                           "detail": detail, "unprompted": unprompted})

    # Briefs — written because an owner added someone, not because anyone asked.
    brief_query = {"workspace_id": ws} if is_owner else {"workspace_id": ws, "user_id": user["id"]}
    async for b in db.briefs.find(brief_query).sort("updated_at", -1).limit(limit):
        who = b.get("person_name") or b.get("person_email") or "a teammate"
        if b.get("status") == "ready":
            body = b.get("brief") or {}
            n = len(body.get("open_questions") or [])
            add(b.get("updated_at"), "brief", f"Wrote an onboarding brief for {who}",
                f"{len(body.get('sections') or [])} sections, {n} open question(s) it could not answer",
                True)
        elif b.get("status") == "generating":
            add(b.get("updated_at"), "brief", f"Researching the project for {who}", "In progress", True)

    # Audits — triggered when a source finished indexing.
    report = await db.gap_reports.find_one({"workspace_id": ws})
    if report and report.get("status") == "ready":
        gaps = report.get("gaps", [])
        draftable = sum(1 for g in gaps if g.get("can_draft"))
        add(report.get("updated_at"), "audit", f"Audited the documentation — {len(gaps)} gap(s)",
            f"{draftable} it offered to write itself", True)

    # The self-interview — run after the sources settled, nobody asked.
    rd = await db.readiness.find_one({"workspace_id": ws})
    if rd and rd.get("status") == "ready":
        missing = rd.get("total", 0) - rd.get("score", 0)
        add(rd.get("updated_at"), "readiness",
            f"Interviewed itself — ready for {rd.get('score', 0)} of {rd.get('total', 0)} first-week questions",
            f"{missing} it could not answer went to the ledger for a person to close" if missing else "It could answer all of them from the sources",
            True)

    # Drafts — these ones a human asked for.
    async for d in db.drafts.find({"workspace_id": ws}).sort("updated_at", -1).limit(limit):
        if d.get("status") == "ready":
            add(d.get("updated_at"), "draft", f"Drafted “{d.get('gap_title') or 'a missing document'}”",
                f"{len((d.get('draft') or {}).get('assumptions') or [])} assumption(s) flagged for review",
                False)

    # Sources landing is what triggers most of the above.
    async for src in db.sources.find({"workspace_id": ws}).sort("updated_at", -1).limit(limit):
        if src.get("status") == "ready":
            add(src.get("updated_at"), "source", f"Indexed {src.get('label')}",
                f"{(src.get('stats') or {}).get('chunks_count', 0)} chunks", False)
        elif src.get("status") == "error":
            add(src.get("updated_at"), "source", f"Could not index {src.get('label')}",
                (src.get("error_message") or "")[:120], False)

    events.sort(key=lambda e: e["at"] or "", reverse=True)
    unprompted = sum(1 for e in events if e["unprompted"])
    return {"events": events[:limit], "unprompted_count": unprompted}
