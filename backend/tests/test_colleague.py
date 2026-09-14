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


# ── Which model answers ───────────────────────────────────────────────────────

def test_model_chain_adds_providers_only_when_their_key_is_set(monkeypatch):
    from agent import agent as a
    monkeypatch.setattr(a.settings, "GROQ_API_KEY", "g")
    monkeypatch.setattr(a.settings, "CEREBRAS_API_KEY", "")
    monkeypatch.setattr(a.settings, "GEMINI_API_KEY", "gm")
    chain = a.model_chain(background=False)
    providers = [c[1] for c in chain]
    assert providers[0] == "groq" and "gemini" in providers and "cerebras" not in providers


def test_pick_model_routes_around_an_exhausted_model(monkeypatch):
    from agent import agent as a
    monkeypatch.setattr(a.settings, "GROQ_API_KEY", "g")
    monkeypatch.setattr(a.settings, "GROQ_FALLBACK_MODELS", "second,third")
    monkeypatch.setattr(a.settings, "GROQ_MODEL", "first")
    a._EXHAUSTED.clear()
    assert a.pick_model(False)[3] == "first"
    a.mark_exhausted("groq/first")
    assert a.pick_model(False)[3] == "second"
    a._EXHAUSTED.clear()



# ── When a model is busy ─────────────────────────────────────────────────────

def test_per_minute_limits_are_told_apart_from_daily_caps():
    from core.errors import is_quota_error, is_rate_limit_error
    minute = "Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` on tokens per minute (TPM)"
    day = "Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` on tokens per day (TPD)"
    assert is_rate_limit_error(minute) and not is_quota_error(minute)
    assert is_quota_error(day)
    assert not is_rate_limit_error("Connection refused")


def test_a_benched_model_comes_back_when_its_time_is_up():
    import time
    from agent import agent as a
    a._EXHAUSTED.clear()
    a.mark_exhausted("groq/x", seconds=0.01)
    assert not a._usable("groq/x")
    time.sleep(0.02)
    assert a._usable("groq/x")
    a._EXHAUSTED.clear()


def test_background_work_uses_the_chat_model_last(monkeypatch):
    from agent import agent as a
    monkeypatch.setattr(a.settings, "GROQ_API_KEY", "g")
    monkeypatch.setattr(a.settings, "CEREBRAS_API_KEY", "")
    monkeypatch.setattr(a.settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(a.settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(a.settings, "GROQ_MODEL", "chat")
    monkeypatch.setattr(a.settings, "GROQ_BACKGROUND_MODEL", "small")
    monkeypatch.setattr(a.settings, "GROQ_FALLBACK_MODELS", "chat,other")
    models = [c[3] for c in a.model_chain(background=True)]
    assert models == ["small", "other", "chat"]


def test_select_relevant_drops_tools_the_question_does_not_touch():
    tools = [_tool("gh_list_issues", "List issues in a repository")] + \
            [_tool(f"gh_thing_{i}", "Something unrelated") for i in range(20)]
    assert select_relevant(tools, "what is the production deploy window", limit=8) == []


def test_unfinished_sign_ins_are_not_opened():
    from toolgrants.registry import GrantSession
    session = GrantSession().open([
        {"_id": "1", "name": "Atlassian", "kind": "mcp_oauth", "status": "authorizing", "url": "https://mcp.example.com/mcp"},
        {"_id": "2", "name": "Broken", "kind": "mcp_http", "status": "error", "url": "https://mcp.example.com/mcp"},
    ])
    assert session.tools == [] and session.clients == [] and session.failed == []



def test_filler_words_do_not_make_a_tool_relevant():
    tools = [_tool("github_list_pull_requests", "List pull requests in a GitHub repository. Use this when you want to know which PRs are open"),
             _tool("github_get_me", "Get details of the authenticated GitHub user"),
             _tool("atlassian_searchConfluenceUsingCql", "Search Confluence pages using CQL")]
    chosen = {t.tool_name for t in select_relevant(tools, "Which Confluence pages do we have about deployment?", limit=2)}
    assert chosen == {"atlassian_searchConfluenceUsingCql"}


def test_output_budget_respects_models_with_small_output_limits(monkeypatch):
    from agent import agent as a
    monkeypatch.setattr(a.settings, "MAX_OUTPUT_TOKENS", 8000)
    assert a.max_output_tokens("qwen/qwen3.8-27b", background=True) == 900
    assert a.max_output_tokens("openai/gpt-oss-120b", background=False) == 2000
    assert a.max_output_tokens("openai/gpt-oss-20b", background=True) == 8000


def test_the_question_is_sent_with_its_passages():
    from chat.routes import _primed
    prompt = _primed("What is the deploy window?", "[1] Source: Confluence: SD\nTuesday to Thursday")
    assert prompt.startswith("What is the deploy window?")
    assert "Tuesday to Thursday" in prompt and "Use a tool only when" in prompt


def test_the_stream_is_drained_in_one_task():
    import asyncio
    from chat.routes import _pump

    async def fine():
        yield {"data": "a"}
        yield {"data": "b"}

    async def throttled():
        yield {"data": "a"}
        raise RuntimeError("429 rate limit")

    async def drain(stream):
        queue = asyncio.Queue()
        await _pump(stream, queue)
        return [queue.get_nowait() for _ in range(queue.qsize())]

    assert [kind for kind, _ in asyncio.run(drain(fine()))] == ["chunk", "chunk", "end"]
    last_kind, last = asyncio.run(drain(throttled()))[-1]
    assert last_kind == "error" and "rate limit" in str(last)


def test_the_wait_a_provider_asks_for_is_read():
    from core.errors import retry_after_seconds
    assert retry_after_seconds("Please try again in 7.7925s. Need more tokens?") == 7.7925
    assert retry_after_seconds("Please try again in 1m12.5s.") == 72.5
    assert retry_after_seconds("try again in 450ms") == 0.45
    assert retry_after_seconds("Rate limit reached") is None


def _throttle_once(a, monkeypatch, chain):
    import asyncio
    from strands.types.exceptions import ModelThrottledException
    a._EXHAUSTED.clear()
    monkeypatch.setattr(a.settings, "LLM_BACKEND", "groq")
    monkeypatch.setattr(a, "model_chain", lambda background: chain)
    monkeypatch.setattr(a, "_build_model", lambda background=False, entry=None: SimpleNamespace(sensei_key=entry[0]))
    notices = []
    hook = a.ModelFailover(max_wait_s=0.2)
    hook.on_notice = notices.append
    event = SimpleNamespace(
        retry=False,
        exception=ModelThrottledException(
            "Rate limit reached for model `m1` on tokens per minute (TPM). Please try again in 7.5s."),
        agent=SimpleNamespace(model=SimpleNamespace(sensei_key=chain[0][0])),
    )
    asyncio.run(hook._after_model_call(event))
    return event, notices


def test_a_throttled_call_moves_to_the_next_model_and_keeps_its_work(monkeypatch):
    from agent import agent as a
    event, notices = _throttle_once(a, monkeypatch, [("groq/m1", "groq", "u", "m1"), ("groq/m2", "groq", "u", "m2")])
    assert event.retry is True
    assert event.agent.model.sensei_key == "groq/m2"
    # The person hears one calm line; which model took over is plumbing, kept out of it.
    assert notices == ["Taking a little longer to check"]
    assert "m1" not in notices[0] and "m2" not in notices[0]
    assert not a.model_available("groq/m1")
    a._EXHAUSTED.clear()


def test_a_long_rest_on_every_model_is_reported_not_waited_out(monkeypatch):
    from agent import agent as a
    event, notices = _throttle_once(a, monkeypatch, [("groq/m1", "groq", "u", "m1")])
    assert event.retry is False
    assert notices == []
    a._EXHAUSTED.clear()


def test_tool_names_are_taken_out_of_the_search():
    from agent.tools import without_tool_names
    assert without_tool_names(
        "Which Confluence pages do we have about deployment, and what is the production deploy window?"
    ) == "Which pages do we have about deployment, and what is the production deploy window?"
    assert without_tool_names("According to Confluence, who is on call the week of 15 September?") == \
        "who is on call the week of 15 September?"
    assert without_tool_names("Who owns the routing worker?") == "Who owns the routing worker?"


def test_rankings_are_interleaved_and_no_page_takes_every_place():
    from agent.tools import interleave

    def row(cid, title, distance):
        return (cid, "doc", {"source_label": "Confluence: personal space", "title": title}, distance)

    noisy = [row("a1", "Getting started", .40), row("a2", "Getting started", .41),
             row("a3", "Getting started", .42), row("b1", "Explore", .43)]
    focused = [row("r1", "Deployment runbook", .50), row("a1", "Getting started", .60)]
    assert [r[0] for r in interleave([focused, noisy], 4, per_page=2)] == ["r1", "a1", "a2", "b1"]


def test_searching_before_the_model_does_not_spend_its_searches(monkeypatch):
    import db.chroma
    from agent.tools import make_search_tool

    class Collection:
        def count(self):
            return 3

        def query(self, query_texts, n_results, include, where=None):
            rows = [(f"c{i}", f"passage {i}", {"source_label": "Confluence: SD", "title": f"Page {i}"}, 0.1 * i)
                    for i in range(3)]
            return {"ids": [[r[0] for r in rows]], "documents": [[r[1] for r in rows]],
                    "metadatas": [[r[2] for r in rows]], "distances": [[r[3] for r in rows]]}

    monkeypatch.setattr(db.chroma, "get_workspace_collection", lambda client, ws: Collection())
    search, _ = make_search_tool("ws", None, n_results=1, budget=1)
    assert "passage 0" in search.unmetered("deploy window")
    assert "budget" not in search(query="release captain").lower()
    assert "budget reached" in search(query="on call").lower()


def test_a_limit_rests_the_model_it_names_not_the_first_in_line(monkeypatch):
    import time
    from agent import agent as a
    a._EXHAUSTED.clear()
    chain = [("groq/openai/gpt-oss-120b", "groq", "u", "openai/gpt-oss-120b"),
             ("groq/openai/gpt-oss-20b", "groq", "u", "openai/gpt-oss-20b")]
    monkeypatch.setattr(a, "model_chain", lambda background: chain)
    key = a.bench_for(Exception(
        "Rate limit reached for model `openai/gpt-oss-20b` on tokens per minute (TPM). Please try again in 13.8s."),
        background=True)
    assert key == "groq/openai/gpt-oss-20b"
    assert a.model_available("groq/openai/gpt-oss-120b")
    assert 13 < a._EXHAUSTED[key] - time.time() <= 15
    a._EXHAUSTED.clear()


def test_claude_answers_first_when_an_anthropic_key_is_set(monkeypatch):
    from agent import agent as a
    monkeypatch.setattr(a.settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(a.settings, "GROQ_API_KEY", "g")
    chat = a.model_chain(background=False)
    background = a.model_chain(background=True)
    assert chat[0][1] == "anthropic" and chat[0][3] == a.settings.ANTHROPIC_MODEL
    assert background[0][3] == a.settings.ANTHROPIC_BACKGROUND_MODEL
    assert chat[1][1] == "groq"
    monkeypatch.setattr(a.settings, "ANTHROPIC_API_KEY", "")
    assert a.model_chain(background=False)[0][1] == "groq"


def test_an_anthropic_entry_builds_a_claude_model(monkeypatch):
    from agent import agent as a
    monkeypatch.setattr(a.settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(a.settings, "LLM_BACKEND", "groq")
    model = a._build_model(background=False, entry=("anthropic/claude-sonnet-5", "anthropic", None, "claude-sonnet-5"))
    assert type(model).__name__ == "AnthropicModel"
    assert model.sensei_key == "anthropic/claude-sonnet-5"
    assert model.config["model_id"] == "claude-sonnet-5" and model.config["max_tokens"] == a.CHAT_OUTPUT_TOKENS


def test_recent_history_keeps_the_last_exchanges_in_order():
    from chat.routes import recent_history
    msgs = [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"}, {"role": "assistant", "content": "", "error": True},
            {"role": "user", "content": "q3"}, {"role": "assistant", "content": "a3"},
            {"role": "user", "content": "q4"}, {"role": "assistant", "content": "x" * 5000},
            {"role": "user", "content": "q5"}]
    h = recent_history(msgs)
    # q2's failed answer is dropped, so q2 and q3 merge into one user turn; the
    # window keeps whole exchanges and ends on an answer, never a dangling question.
    assert [m["role"] for m in h] == ["user", "assistant", "user", "assistant"]
    assert h[0]["content"][0]["text"] == "q2\n\nq3"
    assert h[-1]["content"][0]["text"].endswith("…") and len(h[-1]["content"][0]["text"]) < 1600
    assert recent_history([{"role": "user", "content": "only a question"}]) == []


def test_a_null_from_the_model_reads_as_empty():
    from agent.readiness import Grade, ReadinessGrades
    from meetings.listener import ClaimVerdict, MeetingSummary
    g = ReadinessGrades(grades=[{"question": "q", "answerable": False, "answer": None, "source": None}])
    assert g.grades[0].answer == "" and g.grades[0].source == ""
    assert MeetingSummary(summary="s", decisions=None, action_items=None, open_questions=None).decisions == []
    v = ClaimVerdict(**{k: None for k in ClaimVerdict.model_fields if ClaimVerdict.model_fields[k].annotation is str},
                     **{k: False for k in ClaimVerdict.model_fields if ClaimVerdict.model_fields[k].annotation is bool},
                     **{k: 0.0 for k in ClaimVerdict.model_fields if ClaimVerdict.model_fields[k].annotation is float})
    assert v.correction == ""
