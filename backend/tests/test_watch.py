"""The watcher refreshes the search index when a source changes, not just reports it."""
import pytest

from agent import watch


class _FakeColl:
    def __init__(self, source):
        self.source = source
        self.records = []

    async def update_one(self, filt, update):
        self.records.append((filt, update))
        if update.get("$set"):
            self.source.update(update["$set"])


class _FakeDb:
    def __init__(self, source):
        self.sources = _FakeColl(source)


def _doc(title: str, body: str) -> dict:
    return {"content": body, "metadata": {"title": title}}


async def test_watch_reindexes_changed_source(monkeypatch):
    source = {"_id": "src1", "label": "#general",
              "content_fingerprint": {"Arch": "1111"}}
    db = _FakeDb(source)
    seen = {}

    async def fake_fetch(src):
        return [_doc("Arch", "Version 2 of the plan")]  # same title, new body

    monkeypatch.setattr(watch, "_fetch", fake_fetch)

    async def fake_write(_db, chroma, source_id, docs):
        seen["source_id"] = source_id
        seen["docs"] = docs

    monkeypatch.setattr("agent.ingest.write_source_docs", fake_write)

    result = await watch.check_source(db, object(), source)

    assert result is not None and "Arch" in result["changed"]
    assert seen["source_id"] == "src1"
    assert seen["docs"][0]["content"].startswith("Version 2")
    # Fingerprint only moved after a successful re-index.
    assert source["content_fingerprint"]["Arch"] != "1111"


async def test_watch_keeps_fingerprint_when_reindex_fails(monkeypatch):
    source = {"_id": "src1", "label": "#general",
              "content_fingerprint": {"Arch": "1111"}}
    db = _FakeDb(source)

    async def fake_fetch(src):
        return [_doc("Arch", "Version 2 of the plan")]

    monkeypatch.setattr(watch, "_fetch", fake_fetch)

    async def boom(_db, chroma, source_id, docs):
        raise RuntimeError("chroma down")

    monkeypatch.setattr("agent.ingest.write_source_docs", boom)

    result = await watch.check_source(db, object(), source)

    assert result is None
    stamped = [u for u in db.sources.records
               if "content_fingerprint" in u[1].get("$set", {})]
    assert not stamped  # stale fingerprint → the next cycle retries


async def test_watch_first_sighting_records_baseline_without_reindex(monkeypatch):
    source = {"_id": "src1", "label": "#general"}
    db = _FakeDb(source)
    seen = {"writes": 0}

    async def fake_fetch(src):
        return [_doc("Arch", "Version 1")]

    monkeypatch.setattr(watch, "_fetch", fake_fetch)

    async def fake_write(*_args):
        seen["writes"] += 1

    monkeypatch.setattr("agent.ingest.write_source_docs", fake_write)

    result = await watch.check_source(db, object(), source)

    assert result is None
    assert seen["writes"] == 0  # baseline only; the real ingest already indexed it
    assert "Arch" in source["content_fingerprint"]