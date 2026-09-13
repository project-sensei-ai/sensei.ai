"""
The judgement that makes the agent a colleague rather than a chat box:
which tools it is allowed, which tools it is shown, and when it speaks in a
meeting. None of these call a model.
"""
from types import SimpleNamespace

from meetings.listener import is_addressed, looks_like_an_assertion, strip_address
from toolgrants.registry import WriteGate, classify, enabled_tool_names, select_relevant, slug


# ── Speaking in meetings ──────────────────────────────────────────────────────

def test_addressed_only_when_spoken_to_not_about():
    assert is_addressed("Sensei, what chunk size do we use?")
    assert is_addressed("hey sensei what is the deploy region")
    assert is_addressed("is that right, Sensei?")
    # The product is called Sensei too. A claim about it is not a question to it.
    assert not is_addressed("as far as I know the vector store for Sensei is Pinecone")
    assert not is_addressed("we should add Sensei to the sprint board")


def test_strip_address_leaves_the_question():
    assert strip_address("Hey Sensei, what chunk size do we use?") == "what chunk size do we use"
    assert strip_address("nothing to strip") == "nothing to strip"


def test_assertions_are_statements_of_fact_not_hedges_or_questions():
    assert looks_like_an_assertion("The vector store for this project is Pinecone, so budget for it.")
    assert looks_like_an_assertion("Deploys run on App Runner in us-west-2 these days.")
    assert not looks_like_an_assertion("Is the vector store Pinecone?")
    assert not looks_like_an_assertion("I think the vector store might be Pinecone")
    assert not looks_like_an_assertion("ok lets grab lunch")


# ── What the agent may do ─────────────────────────────────────────────────────

def test_classify_prefers_server_annotations_then_falls_back_to_the_name():
    assert classify("delete_everything", {"readOnlyHint": True}) == "read"
    assert classify("get_thing", {"destructiveHint": True}) == "write"
    assert classify("list_issues") == "read"
    assert classify("create_issue") == "write"
    assert classify("issue_write") == "write"
    assert classify("get_me") == "read"
    assert classify("search_code") == "read"


def test_write_tools_are_off_unless_the_owner_allowed_them():
    grant = {"allow_write": False, "disabled_tools": [],
             "tools": [{"name": "gh_list_issues", "access": "read"},
                       {"name": "gh_create_issue", "access": "write"}]}
    assert enabled_tool_names(grant) == {"gh_list_issues"}
    grant["allow_write"] = True
    assert enabled_tool_names(grant) == {"gh_list_issues", "gh_create_issue"}
    grant["disabled_tools"] = ["gh_create_issue"]
    assert enabled_tool_names(grant) == {"gh_list_issues"}


def test_gate_cancels_only_unpermitted_granted_tools():
    gate = WriteGate(permitted={"github_list_issues"}, grant_names={"github": "GitHub"})

    def event(name):
        return SimpleNamespace(tool_use={"name": name}, cancel_tool=False)

    e = event("github_create_issue"); gate._before(e)
    assert e.cancel_tool and "GitHub" in e.cancel_tool
    e = event("github_list_issues"); gate._before(e)
    assert e.cancel_tool is False
    # Built-in tools are not the gate's business.
    e = event("search_project_docs"); gate._before(e)
    assert e.cancel_tool is False
    assert gate.refusals == [{"tool": "github_create_issue", "grant": "GitHub"}]


def test_slug_is_a_safe_prefix():
    assert slug("GitHub") == "github"
    assert slug("Zapier (prod)") == "zapier_prod"
    assert slug("") == "tool"


# ── Which tools it is shown ───────────────────────────────────────────────────

def _tool(name, desc=""):
    return SimpleNamespace(tool_name=name, mcp_tool=SimpleNamespace(description=desc))


def test_select_relevant_keeps_the_tools_the_question_names():
    tools = [_tool("gh_list_issues", "List issues in a repository"),
             _tool("gh_create_branch", "Create a new branch"),
             _tool("gh_list_pull_requests", "List pull requests"),
             _tool("gh_fork_repository", "Fork a repo"),
             _tool("gh_delete_file", "Delete a file")]
    chosen = select_relevant(tools, "list the open issues and pull requests", limit=2)
    names = {t.tool_name for t in chosen}
    assert names == {"gh_list_issues", "gh_list_pull_requests"}


def test_select_relevant_is_a_no_op_under_the_limit():
    tools = [_tool("a"), _tool("b")]
    assert select_relevant(tools, "anything", limit=5) is tools
