import asyncio
import re
import time
from dataclasses import dataclass, field

from strands import Agent, ModelRetryStrategy
from strands.hooks import AfterInvocationEvent, AfterModelCallEvent, HookProvider, HookRegistry
from strands.types.exceptions import ModelThrottledException

from core.config import settings

# Models that hit their daily cap, with when. Skipped for an hour, then tried
# again — the cap is a rolling window, and a model that was dead at 9am may be
# back by 10. Process-local on purpose: a restart is a fine way to reset it.
_EXHAUSTED: dict[str, float] = {}
_EXHAUSTED_FOR = 3600.0


def mark_exhausted(model_id: str | None, seconds: float = _EXHAUSTED_FOR) -> None:
    """Bench a model: an hour for a daily cap, about a minute for a per-minute limit."""
    if model_id:
        _EXHAUSTED[model_id] = time.time() + seconds
        span = "an hour" if seconds >= 3600 else f"{int(seconds)}s"
        print(f"[models] {model_id} is at its limit — routing around it for {span}")


def _usable(model_id: str) -> bool:
    until = _EXHAUSTED.get(model_id)
    return until is None or time.time() > until


async def retry_on_quota(fn, *args, **kwargs):
    """
    Run a background job; if a model's daily quota ended it, route around that
    model and run it once more. Agents are built inside `fn`, so the retry
    picks up the fallback automatically.
    """
    from core.errors import is_quota_error, model_named_in
    try:
        return await fn(*args, **kwargs)
    except Exception as exc:
        if not is_quota_error(exc):
            raise
        mark_exhausted(pick_groq_model(background=True))
        return await fn(*args, **kwargs)


GROQ_BASE = "https://api.groq.com/openai/v1"

# Output tokens a model will accept per minute, where a provider caps it far
# below the rest. Groq's Qwen models refuse any request whose output budget is
# over 1,000, so asking for the usual 8,000 made them useless as fallbacks.
_OUTPUT_CAPS = {"qwen/qwen3.8-27b": 900, "qwen/qwen3.6-27b": 900}
CHAT_OUTPUT_TOKENS = 2000


def max_output_tokens(model_id: str, background: bool) -> int:
    """A chat answer is a few paragraphs; background reports need more room."""
    wanted = settings.MAX_OUTPUT_TOKENS if background else min(settings.MAX_OUTPUT_TOKENS, CHAT_OUTPUT_TOKENS)
    return min(wanted, _OUTPUT_CAPS.get(model_id, wanted))

# Free, hosted, OpenAI-compatible. Each becomes part of the chain when its key
# is present, so an exhausted Groq day falls through to Cerebras, then Gemini,
# then OpenRouter, without anyone editing a flag.
_PROVIDERS = [
    ("groq", GROQ_BASE, "GROQ_API_KEY", "GROQ_MODEL", "GROQ_BACKGROUND_MODEL"),
    ("cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "CEREBRAS_MODEL", "CEREBRAS_BACKGROUND_MODEL"),
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_BACKGROUND_MODEL"),
    ("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_BACKGROUND_MODEL"),
]


def model_chain(background: bool) -> list[tuple[str, str, str, str]]:
    """(key, provider, base_url, model_id) in the order they should be tried."""
    chain = []
    for name, base, key_env, model_env, bg_env in _PROVIDERS:
        api_key = getattr(settings, key_env, "")
        if not api_key:
            continue
        preferred = getattr(settings, bg_env if background else model_env)
        models = [preferred]
        if name == "groq":
            models += [m.strip() for m in settings.GROQ_FALLBACK_MODELS.split(",") if m.strip()]
            if background:
                # Each Groq model has its own per-minute budget. Background work
                # borrowing the chat model's budget is what leaves a person
                # waiting on a question, so the chat model goes last for it.
                models = [m for m in models if m != settings.GROQ_MODEL] + [settings.GROQ_MODEL]
        for m in models:
            if m not in [c[3] for c in chain if c[1] == name]:
                chain.append((f"{name}/{m}", name, base, m))
    return chain


def pick_model(background: bool) -> tuple[str, str, str, str]:
    """The first (key, provider, base_url, model) in the chain with quota left."""
    chain = model_chain(background)
    if not chain:
        return ("groq/" + settings.GROQ_MODEL, "groq", GROQ_BASE, settings.GROQ_MODEL)
    for entry in chain:
        if _usable(entry[0]):
            return entry
    return chain[0]


def pick_groq_model(background: bool) -> str:
    """Kept for callers that only need the id; the chain may not be Groq at all."""
    return pick_model(background)[0]


def model_available(model_id: str | None) -> bool:
    """True unless the model is resting after hitting a limit."""
    return _usable(model_id)


def seconds_until_available(background: bool) -> float | None:
    """How long until the first model in the chain is back; None when there is no chain."""
    chain = model_chain(background)
    if not chain:
        return None
    now = time.time()
    return max(0.0, min(_EXHAUSTED.get(key, 0.0) - now for key, *_ in chain))


def providers_status() -> list[dict]:
    """What the fallback chain looks like right now — shown on the Trust page."""
    out = []
    for key, provider, _base, model in model_chain(False) + model_chain(True):
        if any(o["key"] == key for o in out):
            continue
        out.append({"key": key, "provider": provider, "model": model, "usable": _usable(key)})
    return out
from .tools import make_inventory_tool, make_search_tool, search_knowledge_base

SENSEI_SYSTEM_PROMPT = """You are Sensei, a colleague on this project — not a chatbot. You were onboarded
by the project owner, who gave you access to the project's sources and, sometimes,
to tools. You think, look things up, do the work, and say plainly what you cannot do.

## What you can reach
- `search_project_docs` — the indexed sources (repos, wiki pages, files, tickets,
  meeting notes). "What does the architecture say?" → search passages.
- `list_project_knowledge` — the catalogue. "Is there a doc about X?" / "what do
  you know?" → read the shelf, not the books.
- `who_did_what` — a person's actual activity: commits, PRs, issues, tickets.
  Use for "what has Priya been working on", "who touched the payments service".
- `jira_search` / `jira_issue` — LIVE Jira. Ticket status is read now, never from
  the index. Say "as of just now" when you report it. (Only present when Jira is
  connected.)
- `create_spreadsheet` / `write_document` — produce a file when someone asks for
  a sheet, a table, a summary doc, a handover note. Gather facts first, then make
  the file once.
- Tools from connected services (GitHub, Slack, Gmail, calendars, internal APIs…)
  appear with the service's name as a prefix, e.g. `github_list_issues`. Use them
  like a colleague with an account would. If a tool call is refused because the
  owner has not allowed writes, say exactly that — do not pretend you did it.

## How to work
- Decide which tool answers the question; do not search when the answer is live
  (ticket status, open PRs) or about a person's work (use who_did_what — a
  question that names a person or bot and asks what they did goes there first).
- A question usually arrives with the passages already retrieved for it, and
  that counts as your first search. Search again only if they genuinely miss
  what the question needs; never a third time with the same intent. If the
  passages and one more search found nothing, the project does not contain it —
  say so and stop.
- Chain tools toward the goal: look up, then act, then report. When asked to "do"
  something, do it — a colleague asked for a spreadsheet produces a spreadsheet.
- Never take a write action (create, send, update, delete) the person did not
  clearly ask for. Read freely; write only on request.

## How to answer
- Direct and specific. Lead with the answer, then the evidence.
- Speak about the project, not about your retrieval: never "the search returned…"
  or "in the results I was given".
- Cite sources inline by label: [my-repo], [Confluence: ENG], [Jira PROJ-412 live].
  Never emit numeric or dagger markers such as 【1†source】 or [1].
- If the sources do not cover it, say so honestly in one sentence. Do not
  fabricate project details, ticket states, owners or decisions.
- Say how fresh a fact is when it matters: "synced from Confluence", "live from
  Jira just now".
- Keep it concise; markdown lists or code blocks where they help.
- A purely general question (no project angle) can be answered directly.
"""


def _build_model(background: bool = False, entry: tuple | None = None):
    """
    The configured model, for any agent in the system.

    Shared so the chat agent and the background agents that write briefs cannot
    drift onto different backends — one LLM_BACKEND flag moves all of them.

    `background=True` selects the cheaper model. Background work is bounded and
    well-specified — survey these sources, compose this object — and there is a
    lot more of it than there is chat.

    `entry` builds one particular model from the chain, which is how a turn
    moves off a model that has hit its limit.
    """
    if settings.LLM_BACKEND == "bedrock":
        import boto3
        from strands.models.bedrock import BedrockModel

        # Credentials in backend/.env are loaded by pydantic-settings, which does
        # not export them to the process environment — so boto3's default chain
        # cannot see them and Bedrock fails with NoCredentialsError even though
        # the keys are right there. Build the session explicitly instead. An IAM
        # role (no keys in .env) still works: boto3 falls back to its own chain.
        session = boto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            region_name=settings.AWS_REGION,
        )
        # The session already carries the region; passing both is rejected.
        return BedrockModel(
            model_id=(settings.BEDROCK_BACKGROUND_MODEL_ID or settings.BEDROCK_MODEL_ID)
            if background else settings.BEDROCK_MODEL_ID,
            boto_session=session,
        )
    if settings.LLM_BACKEND == "ollama":
        from strands.models.openai import OpenAIModel
        return OpenAIModel(
            model_id=settings.OLLAMA_MODEL,
            client_args={"api_key": "ollama", "base_url": settings.OLLAMA_BASE_URL},
        )
    from strands.models.openai import OpenAIModel
    key, provider, base_url, model_id = entry or pick_model(background)
    api_key = {
        "groq": settings.GROQ_API_KEY, "cerebras": settings.CEREBRAS_API_KEY,
        "gemini": settings.GEMINI_API_KEY, "openrouter": settings.OPENROUTER_API_KEY,
    }.get(provider, settings.GROQ_API_KEY)
    model = OpenAIModel(
        model_id=model_id,
        # No silent retries inside the HTTP client: it honours retry-after for up
        # to a minute per attempt, so a throttled question sat on "Searching"
        # for minutes. ModelFailover moves the turn to another model instead,
        # and says so.
        client_args={"api_key": api_key, "base_url": base_url,
                     "max_retries": 0, "timeout": 120.0 if background else 60.0},
        # A structured report of eight gaps is a lot of tokens in one response,
        # and running out mid-object fails the whole run with
        # "unrecoverable state due to max_tokens limit".
        params={"max_tokens": max_output_tokens(model_id, background)},
    )
    # So a quota error can be pinned on the exact provider/model that raised it.
    model.sensei_key = key
    return model


_RETRY = ModelRetryStrategy(max_attempts=3, initial_delay=2, max_delay=8)

_DAILY = re.compile(r"tokens per day|\bTPD\b|daily limit", re.I)


class ModelFailover(HookProvider):
    """
    A per-minute limit on one model is not a limit on the next.

    Groq's free tier gives each model a few thousand tokens a minute, and a turn
    that searches, reads the catalogue and then answers can spend that in two
    calls. When a call is refused, the agent moves onto the next model with room
    and makes the same call again, keeping every passage and tool result it has
    gathered. When every model is resting, it waits for the first one back if
    that is soon, and says so; anything longer is left to the caller to report.
    """

    def __init__(self, *, background: bool = False, max_moves: int = 6, max_wait_s: float = 30.0):
        self.background = background
        self.max_moves = max_moves
        self.max_wait_s = max_wait_s
        self.on_notice = None   # callable(str), set by whoever is streaming the turn
        self._moves = 0

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(AfterModelCallEvent, self._after_model_call)
        registry.add_callback(AfterInvocationEvent, self._after_invocation)

    async def _after_invocation(self, event) -> None:
        self._moves = 0

    def _tell(self, message: str) -> None:
        if self.on_notice is not None:
            try:
                self.on_notice(message)
            except Exception:
                pass

    async def _after_model_call(self, event) -> None:
        from core.errors import is_quota_error, is_rate_limit_error, retry_after_seconds

        exc = event.exception
        if event.retry or exc is None:
            return
        if not (isinstance(exc, ModelThrottledException) or is_quota_error(exc) or is_rate_limit_error(exc)):
            return
        if self._moves >= self.max_moves:
            return
        self._moves += 1
        said = retry_after_seconds(exc)

        if settings.LLM_BACKEND in ("bedrock", "ollama"):
            # One configured model and no chain to move along: back off, retry it.
            await asyncio.sleep(min(said or 4 * 2 ** (self._moves - 1), self.max_wait_s))
            event.retry = True
            return

        current = getattr(event.agent.model, "sensei_key", None)
        text = str(exc)
        if _DAILY.search(text):
            rest = 3600.0
        elif "request too large" in text.lower():
            rest = 600.0
        else:
            rest = (said or 60.0) + 1.0
        mark_exhausted(current, rest)

        entry = next((e for e in model_chain(self.background) if _usable(e[0])), None)
        if entry is None:
            wait = seconds_until_available(self.background)
            if wait is None or wait > self.max_wait_s:
                return
            self._tell(f"Every model is at its per-minute limit. Picking up again in {int(wait) + 1} seconds.")
            await asyncio.sleep(wait + 0.5)
            entry = next((e for e in model_chain(self.background) if _usable(e[0])), None)
            if entry is None:
                return

        if current is None:
            # Not a model this chain built; all that can be done is wait and retry.
            await asyncio.sleep(min(said or 5.0, self.max_wait_s))
        elif entry[0] != current:
            event.agent.model = _build_model(self.background, entry=entry)
            self._tell(f"{_short(current)} is at its limit, so Sensei moved to {_short(entry[0])}.")
        event.retry = True


def _short(key: str) -> str:
    return key.split("/")[-1]


def build_agent(workspace_id: str, chroma_client, session_manager=None,
                allowed_sources: list[str] | None = None):
    """
    Build a Strands Agent for the given workspace.
    Returns (agent, captured_citations_list).
    The citations list is populated in-place when the agent calls search_project_docs.
    Pass session_manager (e.g. S3SessionManager) to give the agent persistent conversation memory.

    allowed_sources restricts what this particular asker can be answered from.
    None means everything — owners, and members the owner has not narrowed.
    """
    search_tool, captured = make_search_tool(
        workspace_id, chroma_client, allowed_sources=allowed_sources
    )
    model = _build_model()

    tools = [search_tool, make_inventory_tool(workspace_id, chroma_client, allowed_sources)]
    if settings.BEDROCK_KB_ID:
        tools.append(search_knowledge_base)

    agent_kwargs = dict(
        model=model,
        tools=tools,
        system_prompt=SENSEI_SYSTEM_PROMPT,
        # The SDK default is 6 attempts backing off 4→8→16→32→64s, so a throttled
        # question sleeps for ~2 minutes before surfacing anything. On a free-tier
        # key that reads as a hang. Fail fast instead: ~14s worst case, then a
        # real error the user can act on.
        retry_strategy=_RETRY,
    )
    if session_manager is not None:
        agent_kwargs["session_manager"] = session_manager

    agent = Agent(**agent_kwargs)
    return agent, captured


@dataclass
class Colleague:
    """
    A fully equipped agent for one person's turn: the Strands Agent, plus the
    side channels a turn fills in — citations, files produced, tool narration —
    and the MCP sessions that must be closed when the turn ends.
    """
    agent: Agent
    search: object = None
    failover: object = None
    citations: list = field(default_factory=list)
    artifacts: list = field(default_factory=list)
    narration: dict = field(default_factory=dict)
    refusals: list = field(default_factory=list)
    unavailable: list = field(default_factory=list)
    _grants: object = None

    def close(self) -> None:
        if self._grants is not None:
            self._grants.close()
            self._grants = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


BUILTIN_NARRATION = {
    "search_project_docs": "Searching the project's documents",
    "list_project_knowledge": "Taking stock of what's indexed",
    "search_knowledge_base": "Searching uploaded files",
    "who_did_what": "Reading the activity records",
    "jira_search": "Checking Jira, live",
    "jira_issue": "Opening the ticket in Jira, live",
    "create_spreadsheet": "Building the spreadsheet",
    "write_document": "Writing the document",
    "recall_meetings": "Going back over the meeting notes",
}


def build_colleague(
    workspace_id: str,
    chroma_client,
    *,
    sources: list[dict],
    grants: list[dict],
    user_id: str,
    session_manager=None,
    allowed_sources: list[str] | None = None,
    question: str = "",
    max_grant_tools: int | None = None,
    grant_session=None,
) -> Colleague:
    """
    Everything the chat agent gets: the index tools, the live Jira tools when a
    credential exists, the work tools, and every tool the owner granted through
    an MCP connection — gated so writes are refused unless allowed.
    """
    from agent.jira import make_jira_tools
    from agent.people import make_people_tool
    from agent.work import make_work_tools
    from toolgrants.registry import GrantSession, select_relevant

    # Sized for free-tier per-minute token budgets: every passage is re-sent on
    # each model call in the turn, so two searches of six short passages keep a
    # whole turn inside one model's budget.
    search_tool, captured = make_search_tool(workspace_id, chroma_client, n_results=5,
                                             passage_chars=600, budget=3,
                                             allowed_sources=allowed_sources)
    tools = [
        search_tool,
        make_inventory_tool(workspace_id, chroma_client, allowed_sources),
        make_people_tool(workspace_id, chroma_client, allowed_sources),
    ]
    if settings.BEDROCK_KB_ID:
        tools.append(search_knowledge_base)

    # Jira rides on whatever Atlassian credential is already connected, but a
    # member the owner has narrowed away from that source should not get it.
    visible = [s for s in sources if allowed_sources is None or s["_id"] in allowed_sources]
    tools.extend(make_jira_tools(visible))

    work_tools, produced = make_work_tools(workspace_id, user_id)
    tools.extend(work_tools)

    narration = dict(BUILTIN_NARRATION)
    failover = ModelFailover()
    hooks = [failover]
    refusals: list = []
    if grants and grant_session is None:
        # Callers normally pass a warm session from toolgrants.pool; opening
        # here is the fallback for one-off use (tests, scripts).
        grant_session = GrantSession().open(grants)
    if grant_session is not None:
        limit = max_grant_tools if max_grant_tools is not None else settings.MAX_GRANT_TOOLS_PER_TURN
        tools.extend(select_relevant(grant_session.tools, question, limit))
        narration.update(grant_session.narration)
        gate = grant_session.gate(on_refusal=lambda name, g: refusals.append({"tool": name, "grant": g}))
        hooks.append(gate)

    kwargs = dict(
        model=_build_model(),
        tools=tools,
        system_prompt=SENSEI_SYSTEM_PROMPT,
        # ModelFailover handles limits by moving to another model; the SDK's
        # own retries, which sleep on the same one, stay off.
        retry_strategy=None,
    )
    if hooks:
        kwargs["hooks"] = hooks
    if session_manager is not None:
        kwargs["session_manager"] = session_manager

    col = Colleague(
        agent=Agent(**kwargs),
        search=search_tool,
        failover=failover,
        citations=captured,
        artifacts=produced,
        narration=narration,
        refusals=refusals,
        unavailable=grant_session.failed if grant_session else [],
    )
    # The session belongs to the pool, not to this turn — closing it here would
    # tear down a connection every other turn is about to use.
    col._grants = None
    return col


def make_session_manager(session_id: str):
    """
    Return an S3SessionManager for the given session ID, or None if not configured.
    Used for agent conversation memory — the agent recalls prior turns in the same session.
    """
    if not settings.S3_SESSION_BUCKET:
        return None
    try:
        from strands.session.s3_session_manager import S3SessionManager
        return S3SessionManager(
            bucket_name=settings.S3_SESSION_BUCKET,
            session_id=session_id,
            region_name=settings.AWS_REGION,
        )
    except Exception:
        return None
