"""The Slack connector — mrkdwn stripping is the one place parsing can break."""
import agent.tools as tools
from sources.routes import SlackSourceIn


# ── mrkdwn → text ────────────────────────────────────────────────────────────

def test_mrkdwn_drops_labelled_mentions_and_links():
    out = tools._strip_mrkdwn(
        "Hi <@U123|Adi> read <https://docs.example.com/x|the plan> <https://raw.example.com/y>",
        {},
    )
    assert out == "Hi Adi read the plan https://raw.example.com/y"


def test_mrkdwn_resolves_bare_mentions_through_the_user_map():
    out = tools._strip_mrkdwn("<@U123> saw <@U456|Priya>", {"U123": "Kiran"})
    assert "Kiran" in out
    assert "Priya" in out
    assert "<@U" not in out


def test_mrkdwn_unknown_mention_falls_back_to_the_id():
    out = tools._strip_mrkdwn("ping <@U999>", {})
    assert out == "ping U999"


# ── Channel normalisation ────────────────────────────────────────────────────

def test_channel_accepts_with_and_without_hash():
    assert SlackSourceIn(type="slack", token="xoxb-x", channel="# General ").channel == "general"
    assert SlackSourceIn(type="slack", token="xoxb-x", channel="kanban").channel == "kanban"


def test_empty_channel_is_rejected():
    try:
        SlackSourceIn(type="slack", token="xoxb-x", channel="#")
        assert False, "should have raised"
    except ValueError as exc:
        assert "Enter a channel" in str(exc)


# ── fetch_slack maps messages and replies into documents ─────────────────────

class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    """One page of users and history: a top-level message with a 1-reply thread."""

    def __init__(self, **_kwargs):
        self.calls = []

    async def get(self, url, params=None):
        self.calls.append((url, params))
        if url.endswith("users.list"):
            return _FakeResponse({"ok": True, "members": [
                {"id": "U1", "deleted": False, "name": "adi", "profile": {"display_name": "Aditya"}},
                {"id": "U2", "deleted": True},
            ]})
        if url.endswith("conversations.history"):
            return _FakeResponse({"ok": True, "messages": [
                {"type": "message", "user": "U1", "ts": "1611578988.000200",
                 "text": "Let's go with <https://x.dev|plan B>",
                 "reply_count": 1},
                {"type": "message", "user": "U2", "ts": "1611579100.000100",
                 "thread_ts": "1611578988.000200", "text": "a thread reply, ignore here"},
            ]})
        if url.endswith("conversations.replies"):
            return _FakeResponse({"ok": True, "messages": [
                {"user": "U1", "ts": "1611578988.000200", "text": "parent again"},
                {"user": "U2", "ts": "1611579100.000100", "text": "I agree with plan B"},
            ]})
        raise AssertionError(f"unexpected URL {url}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def test_fetch_slack_builds_message_and_reply_docs(monkeypatch):
    monkeypatch.setattr(tools.httpx, "AsyncClient", _FakeClient)
    docs = await tools.fetch_slack(
        bot_token="xoxb-t", channel_id="C1", channel_name="general", team_domain="acme",
    )

    # 1 top-level message (author resolved from the user map) + 1 real reply.
    assert len(docs) == 2

    msg, reply = docs
    assert msg["metadata"]["data_type"] == "message"
    assert msg["metadata"]["author"] == "Aditya"
    assert msg["metadata"]["title"] == "Aditya in #general"
    assert "plan B" in msg["content"]
    assert msg["metadata"]["url"].startswith("https://acme.slack.com/archives/C1/1611578988")

    assert reply["metadata"]["data_type"] == "reply"
    assert reply["metadata"]["author"] == "U2"  # deleted user stayed as raw id
    assert "I agree with plan B" in reply["content"]


async def test_fetch_slack_fails_on_a_bad_token(monkeypatch):
    class _BadClient(_FakeClient):
        async def get(self, url, params=None):
            if url.endswith("users.list"):
                return _FakeResponse({"ok": False, "error": "invalid_auth"})
            raise AssertionError(url)

    monkeypatch.setattr(tools.httpx, "AsyncClient", _BadClient)
    try:
        await tools.fetch_slack(bot_token="bad", channel_id="C1",
                                channel_name="general", team_domain="acme")
        assert False, "should have raised"
    except RuntimeError as exc:
        assert "invalid_auth" in str(exc)