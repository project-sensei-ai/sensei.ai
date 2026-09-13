"""
Trust & access — what the agent can reach, who granted it, and how to stop it.

Every other screen answers "what does it know". This one answers the question a
person actually hesitates over before connecting anything: *what did I just give
it, and can I take it back*.

It is assembled from what is already true rather than from a policy document.
Each connector reports its own ceiling — the most the credential could reach —
alongside the floor we actually read, because a product that shows only the
floor is telling a comfortable half-truth.
"""
from fastapi import APIRouter, Depends

from auth.deps import get_current_user
from core import secrets
from db.chroma import get_chroma, get_workspace_collection
from db.database import get_db
from db.membership import OWNER_ROLES, require_workspace
from db.models import _iso
from fastapi import Request

router = APIRouter(tags=["trust"])


# What each connector's credential could reach, versus what Sensei reads.
# Kept beside the code that uses it so it cannot quietly drift from reality.
GRANTS = {
    "github": {
        "credential": "Personal access token",
        "ceiling": "Every repository this token's account can see",
        "floor": "One repository — files, commits, contributors, collaborators, PRs, issues, releases, CI workflows",
        "cannot": ["Write anything", "Any repo other than the one named", "Private repos the token's account cannot see"],
        "revoke": "Delete this source, or revoke the token on GitHub",
        "improve": "A GitHub App installed per repository would make the ceiling equal the floor",
    },
    "confluence": {
        "credential": "Atlassian API token",
        "ceiling": "Everything the token's Atlassian account can see across the site",
        "floor": "Pages in the one space named here",
        "cannot": ["Write or comment", "Spaces other than the one named", "Jira issues"],
        "revoke": "Delete this source, or revoke the token at id.atlassian.com",
        "improve": "A dedicated Atlassian account invited only to this space makes the limit one Confluence enforces, not one we promise",
    },
    "url": {
        "credential": "None",
        "ceiling": "Public web pages only",
        "floor": "The exact URLs listed",
        "cannot": ["Anything behind a login", "Pages not listed", "Any internal system"],
        "revoke": "Delete this source",
        "improve": None,
    },
    "file": {
        "credential": "None",
        "ceiling": "The uploaded file, nothing else",
        "floor": "The uploaded file",
        "cannot": ["Reach any system", "See anything not uploaded"],
        "revoke": "Delete this source — its vectors go with it",
        "improve": None,
    },
}


@router.get("")
async def overview(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    workspace, role = await require_workspace(user, db)
    ws = workspace["_id"]
    is_owner = role in OWNER_ROLES

    # ── What it can reach ─────────────────────────────────────────────────────
    grants = []
    async for src in db.sources.find({"workspace_id": ws}).sort("created_at", 1):
        spec = GRANTS.get(src["type"], {})
        grants.append({
            "id": src["_id"],
            "type": src["type"],
            "label": src.get("label"),
            "status": src.get("status"),
            "connected_at": _iso(src.get("created_at")),
            "chunks": (src.get("stats") or {}).get("chunks_count", 0),
            # Owners see how the credential is held; members do not need to.
            "credential_state": secrets.status(src.get("config_secret")) if is_owner else None,
            **spec,
        })

    # ── Who can ask ───────────────────────────────────────────────────────────
    members = [m async for m in db.members.find({"workspace_id": ws})]
    user_ids = [m["user_id"] for m in members]
    users = {u["_id"]: u async for u in db.users.find({"_id": {"$in": user_ids}})}
    people = [{
        "name": (users.get(m["user_id"]) or {}).get("name"),
        "email": (users.get(m["user_id"]) or {}).get("email"),
        "role": m.get("role", "member"),
        "status": m.get("status", "active"),
    } for m in members]

    # ── What it actually holds ────────────────────────────────────────────────
    try:
        collection = get_workspace_collection(get_chroma(request), ws)
        indexed_chunks = collection.count()
    except Exception:
        indexed_chunks = 0

    return {
        "workspace": {"name": workspace.get("name"), "role": role},
        "grants": grants,
        "people": people,
        "coverage": {
            "sources": len(grants),
            "indexed_chunks": indexed_chunks,
            "people_with_access": sum(1 for p in people if p["status"] == "active"),
            "pending_invites": sum(1 for p in people if p["status"] != "active"),
        },
        # The half that earns the trust: stated plainly, and true of the build.
        "never": [
            "Reads anything outside the sources listed here",
            "Writes to any connected system — every connector is read-only",
            "Answers anyone who is not on the list above",
            "Stores credentials in plain text"
            if all(g.get("credential_state") in (None, "none", "encrypted") for g in grants)
            else "Stores credentials in plain text (⚠ some sources predate encryption — reconnect them)",
            "Sends your project data to anyone but the configured model provider",
        ],
        "encryption_configured": secrets.is_configured(),
        "can_manage": is_owner,
    }
