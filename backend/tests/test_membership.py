"""
The access boundary.

Every route that touches workspace data resolves through these two functions, so
a mistake here is a mistake everywhere. Worth testing without a database.
"""
import pytest
from fastapi import HTTPException

from db.membership import member_doc, require_owner, require_workspace


class FakeCollection:
    def __init__(self, rows): self.rows = rows; self.inserted = []

    async def find_one(self, query):
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                return row
        return None

    async def insert_one(self, doc): self.inserted.append(doc)


class FakeDB:
    def __init__(self, members=(), workspaces=()):
        self.members = FakeCollection(list(members))
        self.workspaces = FakeCollection(list(workspaces))


OWNER = {"id": "u-owner", "email": "owner@example.com"}
MEMBER = {"id": "u-member", "email": "member@example.com"}
WS = {"_id": "ws-1", "owner_id": "u-owner", "name": "Apollo"}


@pytest.mark.asyncio
async def test_active_member_resolves_their_workspace():
    db = FakeDB([{"user_id": "u-member", "workspace_id": "ws-1", "role": "member",
                  "status": "active"}], [WS])
    workspace, role = await require_workspace(MEMBER, db)
    assert workspace["_id"] == "ws-1" and role == "member"


@pytest.mark.asyncio
async def test_a_pending_invite_is_not_access():
    """Added to the allowlist is not the same as having accepted."""
    db = FakeDB([{"user_id": "u-member", "workspace_id": "ws-1", "role": "member",
                  "status": "invited"}], [WS])
    with pytest.raises(HTTPException) as exc:
        await require_workspace(MEMBER, db)
    assert exc.value.status_code == 403
    assert "still pending" in exc.value.detail


@pytest.mark.asyncio
async def test_a_stranger_has_no_workspace():
    db = FakeDB([], [WS])
    with pytest.raises(HTTPException) as exc:
        await require_workspace({"id": "nobody", "email": "x@y.com"}, db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_a_member_cannot_do_owner_things():
    db = FakeDB([{"user_id": "u-member", "workspace_id": "ws-1", "role": "member",
                  "status": "active"}], [WS])
    with pytest.raises(HTTPException) as exc:
        await require_owner(MEMBER, db, "add team members")
    assert exc.value.status_code == 403
    # The message names the attempted action, rather than something unrelated.
    assert "add team members" in exc.value.detail


@pytest.mark.asyncio
async def test_an_owner_can():
    db = FakeDB([{"user_id": "u-owner", "workspace_id": "ws-1", "role": "owner",
                  "status": "active"}], [WS])
    assert (await require_owner(OWNER, db))["_id"] == "ws-1"


@pytest.mark.asyncio
async def test_a_legacy_workspace_backfills_its_owner():
    """Workspaces predating the members collection must keep working."""
    db = FakeDB([], [WS])
    workspace, role = await require_workspace(OWNER, db)
    assert workspace["_id"] == "ws-1" and role == "owner"
    assert db.members.inserted and db.members.inserted[0]["role"] == "owner"


def test_an_invited_member_is_not_active_until_they_accept():
    doc = member_doc("ws-1", "u-1", "member", invited_by="u-owner", status="invited")
    assert doc["status"] == "invited" and doc["joined_at"] is None
