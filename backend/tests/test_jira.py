"""The Jira connector — ADF flattening is the one place the parsing can break."""
import agent.tools as tools
from sources.routes import JiraSourceIn


# ── ADF → text ───────────────────────────────────────────────────────────────

def test_adf_flattens_paragraphs_and_inline_marks():
    doc = {"type": "doc", "content": [
        {"type": "paragraph", "content": [
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "bold", "marks": [{"type": "strong"}]},
            {"type": "hardBreak"},
            {"type": "text", "text": "world"},
        ]},
        {"type": "paragraph", "content": [
            {"type": "text", "text": "Second para"},
        ]},
    ]}
    out = tools._adf_text(doc)
    assert "Hello bold" in out
    assert "world" in out
    assert "Second para" in out
    assert out.count("\n") >= 2  # both paragraphs end their line


def test_adf_mentions_and_emoji_carry_their_text():
    doc = {"type": "doc", "content": [
        {"type": "paragraph", "content": [
            {"type": "mention", "attrs": {"text": "@aditya"}},
            {"type": "text", "text": " "},
            {"type": "emoji", "attrs": {"text": ":tada:"}},
        ]},
    ]}
    assert "@aditya" in tools._adf_text(doc)
    assert ":tada:" in tools._adf_text(doc)


def test_adf_lists_end_up_as_lines():
    doc = {"type": "doc", "content": [
        {"type": "bulletList", "content": [
            {"type": "listItem", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "one"}]},
            ]},
            {"type": "listItem", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "two"}]},
            ]},
        ]},
    ]}
    assert tools._adf_text(doc).count("one") == 1


# ── Site URL normalisation ───────────────────────────────────────────────────

def test_a_pasted_ticket_url_is_trimmed_to_the_site():
    src = JiraSourceIn(
        type="jira", base_url="https://charanb.atlassian.net/browse/PROJ-42",
        email="a@b.com", api_token="x", project_key="ENG",
    )
    assert src.base_url == "https://charanb.atlassian.net"


def test_a_bare_site_url_is_left_alone():
    src = JiraSourceIn(
        type="jira", base_url="https://charanb.atlassian.net/",
        email="a@b.com", api_token="x", project_key="ENG",
    )
    assert src.base_url == "https://charanb.atlassian.net"


def test_a_redirect_url_with_query_string_is_trimmed():
    src = JiraSourceIn(
        type="jira", base_url="https://charanb.atlassian.net?continue=https%3A%2F%2Fcharanb.atlassian.net%2Fwelcome",
        email="a@b.com", api_token="x", project_key="ENG",
    )
    assert src.base_url == "https://charanb.atlassian.net"


def test_a_name_is_rejected_with_a_usable_message():
    try:
        JiraSourceIn(type="jira", base_url="sai charan",
                     email="a@b.com", api_token="x", project_key="ENG")
        assert False, "should have raised"
    except ValueError as exc:
        assert "must be a URL" in str(exc)


# ── fetch_jira maps issues and comments into documents ──────────────────────

class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    """Two pages of issues, each with one ticket and one comment."""

    def __init__(self, **_kwargs):
        self._issues = [
            {"key": "ENG-1", "fields": {
                "summary": "Fix login",
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "assignee": {"displayName": "Aditya"},
                "labels": ["auth"],
                "customfield_10019": {"value": "Squad B"},
                "description": {"type": "doc", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Broken since v2"}]},
                ]},
                "comment": {"comments": [
                    {"body": {"type": "doc", "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "Reproduced locally"}]},
                    ]}, "author": {"displayName": "Charan"}},
                ]},
            }},
            {"key": "ENG-2", "fields": {
                "summary": "Add logout",
                "status": {"name": "To Do"},
                "priority": {"name": "Low"},
                "assignee": None,
                "labels": [],
                "description": None,
                "comment": {"comments": []},
            }},
        ]

    async def get(self, url, params=None):
        if url.endswith("/rest/api/3/field"):
            return _FakeResponse([
                {"id": "customfield_10019", "name": "Team", "custom": True},
            ])
        assert url.endswith("/rest/api/3/search"), url
        start = params.get("startAt", 0)
        batch = self._issues[:1] if start == 0 else self._issues[1:]
        return _FakeResponse({
            "total": 2,
            "issues": batch,
        })

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def test_fetch_jira_paginates_and_builds_documents(monkeypatch):
    monkeypatch.setattr(tools.httpx, "AsyncClient", _FakeClient)
    docs = await tools.fetch_jira(
        base_url="https://charanb.atlassian.net",
        email="a@b.com", api_token="x", project_key="eng",
    )

    # 2 issues + 1 comment
    assert len(docs) == 3

    issue = docs[0]
    assert issue["metadata"]["data_type"] == "issue"
    assert issue["metadata"]["title"] == "ENG-1: Fix login"
    assert issue["metadata"]["url"] == "https://charanb.atlassian.net/browse/ENG-1"
    assert "Broken since v2" in issue["content"]
    assert "Status: In Progress" in issue["content"]
    # Custom fields from the list view make it into the document.
    assert "Team: Squad B" in issue["content"]

    comment = docs[1]
    assert comment["metadata"]["data_type"] == "comment"
    assert comment["metadata"]["issue_key"] == "ENG-1"
    assert "Reproduced locally" in comment["content"]


# ── Fallback when the search index is missing (410 Gone) ─────────────────────
# Some brand-new cloud sites have no JQL index yet; /search answers 410 Gone
# and the agile board endpoint is the only issue source that still works.

def _raise_gone():
    import httpx
    request = httpx.Request("GET", "http://test")
    raise httpx.HTTPStatusError(
        "Server error '410 Gone' for url",
        request=request,
        response=httpx.Response(410, request=request),
    )


class _SearchGoneClient:
    """/search always 410s; issues come back through /rest/agile board #7."""

    def __init__(self, **_kwargs):
        self._issues = [
            {"key": "ENG-1", "fields": {
                "summary": "Fix login",
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "assignee": {"displayName": "Aditya"},
                "labels": ["auth"],
                "description": None,
                "comment": {"comments": []},
            }},
            {"key": "ENG-2", "fields": {
                "summary": "Add logout",
                "status": {"name": "To Do"},
                "priority": {"name": "Low"},
                "assignee": None,
                "labels": [],
                "description": None,
                "comment": {"comments": []},
            }},
        ]

    async def get(self, url, params=None):
        if url.endswith("/rest/api/3/field"):
            return _FakeResponse([{"id": "customfield_10019", "name": "Team", "custom": True}])
        if url.endswith("/rest/api/3/search"):
            gone = _FakeResponse({}, status=410)
            gone.raise_for_status = _raise_gone
            return gone
        if url.endswith("/rest/agile/1.0/board"):
            assert params == {"projectKeyOrId": "ENG"}
            return _FakeResponse({"values": [{"id": 7}]})
        if "/rest/agile/1.0/board/7/issue" in url:
            return _FakeResponse({"total": len(self._issues), "issues": self._issues})
        raise AssertionError(f"unexpected URL {url}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def test_fetch_jira_falls_back_to_board_when_search_is_gone(monkeypatch):
    monkeypatch.setattr(tools.httpx, "AsyncClient", _SearchGoneClient)
    docs = await tools.fetch_jira(
        base_url="https://charanb.atlassian.net",
        email="a@b.com", api_token="x", project_key="eng",
    )
    assert [d["metadata"]["title"] for d in docs] == ["ENG-1: Fix login", "ENG-2: Add logout"]