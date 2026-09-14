"""Sensei in Slack: authenticity, what it hears, when it speaks."""
import asyncio
import hashlib
import hmac
import time
from types import SimpleNamespace

from slack_channel import service


def test_only_a_request_slack_signed_passes():
    body = b'{"type":"event_callback"}'
    ts = str(int(time.time()))
    good = "v0=" + hmac.new(b"s3cret", f"v0:{ts}:".encode() + body, hashlib.sha256).hexdigest()
    assert service.verify_signature("s3cret", ts, body, good)
    assert not service.verify_signature("s3cret", ts, body, "v0=deadbeef")
    assert not service.verify_signature("s3cret", str(int(time.time()) - 900), body, good)
    assert not service.verify_signature("", ts, body, good)


def test_mentions_are_recognised_and_removed():
    assert service.strip_mentions("<@U0BOT> who is on call this week?", "U0BOT") == ("who is on call this week?", True)
    assert service.strip_mentions("who is on call this week? <@U0OTHER>", "U0BOT") == ("who is on call this week?", False)
    assert service.strip_mentions("Sensei, what's the deploy window?", "U0BOT") == ("what's the deploy window?", True)


def test_answers_are_written_the_way_slack_reads_them():
    assert service.to_mrkdwn("**Priya Nair** leads it.\n- one\n- two") == "*Priya Nair* leads it.\n• one\n• two"


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def __aiter__(self):
        async def gen():
            for r in self._rows:
                yield r
        return gen()


class _Sources:
    def __init__(self, rows):
        self.rows = rows

    def find(self, query=None):
        return _Cursor([r for r in self.rows if not query or all(r.get(k) == v for k, v in query.items())])

    async def find_one(self, query):
        return next((r for r in self.rows if all(r.get(k) == v for k, v in query.items())), None)

    async def update_one(self, *a, **k):
        return None


class _Replies:
    def __init__(self):
        self.rows = []

    async def insert_one(self, doc):
        self.rows.append(doc)


def _db():
    return SimpleNamespace(
        sources=_Sources([{"_id": "src1", "type": "slack", "workspace_id": "ws1",
                           "config": {"channel_id": "C1", "channel_name": "all-sensei", "team_domain": "sensei"}}]),
        slack_replies=_Replies(),
    )


def _wire(monkeypatch, answer="**Priya Nair** leads Sev-2 escalations, per the playbook.", citations=None):
    posted, gaps = [], []
    ident = {"source_id": "src1", "workspace_id": "ws1", "token": "t", "team_id": "T1", "bot_user_id": "UBOT",
             "channel_id": "C1", "channel_name": "all-sensei", "team_domain": "sensei", "at": time.time()}
    monkeypatch.setattr(service, "_identity", lambda source: _coro(ident))
    monkeypatch.setattr(service, "index_live_message", lambda *a, **k: _coro(None))
    monkeypatch.setattr(service, "answer_in_workspace",
                        lambda db, chroma, ws, q: _coro((answer, citations if citations is not None else [{"title": "Apollo — Customer escalation playbook"}])))
    monkeypatch.setattr(service, "post_reply", lambda token, channel, ans, cites, thread_ts=None: (posted.append((channel, ans, thread_ts)), _coro("1.2"))[1])
    monkeypatch.setattr(service, "record_gap", lambda db, ws, q, a: (gaps.append(q), _coro(None))[1])
    monkeypatch.setattr(service, "get_workspace_collection", lambda chroma, ws: None)
    service._SEEN.clear()
    return posted, gaps


async def _coro(value):
    return value


def _event(kind="app_mention", text="<@UBOT> who leads a Sev-2 escalation?", user="U42", event_id="Ev1", **extra):
    ev = {"type": kind, "text": text, "user": user, "channel": "C1", "ts": "1700000000.000100", **extra}
    return {"type": "event_callback", "team_id": "T1", "event_id": event_id, "event": ev}


def test_a_mention_is_answered_in_its_thread(monkeypatch):
    posted, gaps = _wire(monkeypatch)
    db = _db()
    out = asyncio.run(service.handle_event(db, None, _event()))
    assert out["outcome"] == "posted"
    assert posted == [("C1", "**Priya Nair** leads Sev-2 escalations, per the playbook.", "1700000000.000100")]
    assert db.slack_replies.rows[-1]["mode"] == "mentioned" and db.slack_replies.rows[-1]["posted"]
    assert gaps == []


def test_a_direct_message_is_answered_without_a_thread(monkeypatch):
    posted, _ = _wire(monkeypatch)
    out = asyncio.run(service.handle_event(_db(), None, _event("message", "who leads a Sev-2 escalation?", channel_type="im", event_id="Ev2")))
    assert out["outcome"] == "posted" and posted[0][2] is None


def test_chatter_and_the_bots_own_words_are_left_alone(monkeypatch):
    posted, _ = _wire(monkeypatch)
    db = _db()
    assert asyncio.run(service.handle_event(db, None, _event("message", "lunch anyone?", event_id="Ev3")))["outcome"] == "silent"
    assert asyncio.run(service.handle_event(db, None, _event("message", "who leads a Sev-2 escalation?", user="UBOT", event_id="Ev4")))["reason"] == "Sensei's own message"
    assert asyncio.run(service.handle_event(db, None, _event("message", "<@UBOT> hi", event_id="Ev5")))["reason"] == "handled as a mention"
    assert asyncio.run(service.handle_event(db, None, _event(event_id="Ev1")))["reason"] != "duplicate delivery"
    assert asyncio.run(service.handle_event(db, None, _event(event_id="Ev1")))["reason"] == "duplicate delivery"
    assert posted == [] or all(p[1] for p in posted)


def test_an_unprompted_question_needs_a_citation_to_be_posted(monkeypatch):
    from channels import router
    monkeypatch.setattr(router, "best_match_score", lambda text, collection: 0.9)
    posted, _ = _wire(monkeypatch, answer="The sources do not say who leads it.", citations=[])
    out = asyncio.run(service.handle_event(_db(), None, _event("message", "who leads a Sev-2 escalation?", event_id="Ev6")))
    assert out["outcome"] == "silent" and posted == []
    posted, _ = _wire(monkeypatch)
    out = asyncio.run(service.handle_event(_db(), None, _event("message", "who leads a Sev-2 escalation?", event_id="Ev7")))
    assert out["outcome"] == "posted" and posted[0][2] == "1700000000.000100"


def test_a_mention_it_cannot_answer_goes_to_the_ledger(monkeypatch):
    posted, gaps = _wire(monkeypatch, answer="The project's sources do not cover the 2027 office budget.", citations=[])
    out = asyncio.run(service.handle_event(_db(), None, _event(text="<@UBOT> what is the 2027 office budget?", event_id="Ev8")))
    assert out["outcome"] == "posted" and gaps == ["what is the 2027 office budget?"]


def test_a_team_nobody_connected_is_ignored(monkeypatch):
    _wire(monkeypatch)
    payload = _event(event_id="Ev9"); payload["team_id"] = "T-other"
    assert asyncio.run(service.handle_event(_db(), None, payload))["reason"] == "no project is connected to this Slack team"


def test_an_honest_i_dont_see_counts_as_a_refusal():
    from answers.store import looks_like_a_refusal
    assert looks_like_a_refusal("I don't see a budget for a 2027 office move in the project sources.")
    assert looks_like_a_refusal("That is not in the project sources.")
    assert not looks_like_a_refusal("Production deploys happen Tuesday to Thursday.")
