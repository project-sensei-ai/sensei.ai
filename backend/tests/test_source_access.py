"""
What one person can be answered from.

The project boundary decides who may ask at all. This decides what they see once
inside — and getting it wrong means either a leak or an agent that refuses
everyone.
"""
import pytest

from db.membership import visible_sources


class FakeCollection:
    def __init__(self, rows): self.rows = list(rows)

    async def find_one(self, query):
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                return row
        return None

    def find(self, query=None):
        rows = self.rows
        async def gen():
            for r in rows:
                yield r
        return gen()


class FakeDB:
    def __init__(self, members=(), sources=()):
        self.members = FakeCollection(members)
        self.sources = FakeCollection(sources)


SOURCES = [{"_id": "s1"}, {"_id": "s2"}, {"_id": "s3"}]


async def test_an_owner_sees_everything():
    """They chose what to connect; narrowing them would be theatre."""
    db = FakeDB([{"workspace_id": "w", "user_id": "u", "role": "owner"}], SOURCES)
    assert await visible_sources(db, "w", "u") is None


async def test_an_unrestricted_member_sees_everything():
    """The default has to be open, or nobody can ask anything until granted."""
    db = FakeDB([{"workspace_id": "w", "user_id": "u", "role": "member",
                  "source_access": None}], SOURCES)
    assert await visible_sources(db, "w", "u") is None


async def test_a_restricted_member_sees_only_what_was_granted():
    db = FakeDB([{"workspace_id": "w", "user_id": "u", "role": "member",
                  "source_access": ["s1", "s3"]}], SOURCES)
    assert await visible_sources(db, "w", "u") == ["s1", "s3"]


async def test_a_deleted_source_cannot_leave_a_dangling_grant():
    """s9 was revoked from the project; the grant must not resurrect it."""
    db = FakeDB([{"workspace_id": "w", "user_id": "u", "role": "member",
                  "source_access": ["s1", "s9"]}], SOURCES)
    assert await visible_sources(db, "w", "u") == ["s1"]


async def test_granting_nothing_means_nothing():
    """An empty list is a real answer, and must not be read as 'all'."""
    db = FakeDB([{"workspace_id": "w", "user_id": "u", "role": "member",
                  "source_access": []}], SOURCES)
    assert await visible_sources(db, "w", "u") == []


async def test_someone_who_is_not_on_the_project():
    db = FakeDB([], SOURCES)
    assert await visible_sources(db, "w", "nobody") is None
