from dataclasses import dataclass, field

from strands import Agent, ModelRetryStrategy

from core.config import settings
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
  (ticket status, open PRs) or about a person (use who_did_what).
- Search **once**; a second time only if the first genuinely missed; never a third
  with the same intent. If two searches found nothing, the project does not
  contain it — say so and stop.
- Chain tools toward the goal: look up, then act, then report. When asked to "do"
  something, do it — a colleague asked for a spreadsheet produces a spreadsheet.
- Never take a write action (create, send, update, delete) the person did not
  clearly ask for. Read freely; write only on request.

## How to answer
- Direct and specific. Lead with the answer, then the evidence.
- Cite sources inline by label: [my-repo], [Confluence: ENG], [Jira PROJ-412 live].
  Never emit numeric or dagger markers such as 【1†source】 or [1].
- If the sources do not cover it, say so honestly in one sentence. Do not
  fabricate project details, ticket states, owners or decisions.
- Say how fresh a fact is when it matters: "synced from Confluence", "live from
  Jira just now".
- Keep it concise; markdown lists or code blocks where they help.
- A purely general question (no project angle) can be answered directly.
"""


def _build_model(background: bool = False):
    """
    The configured model, for any agent in the system.

    Shared so the chat agent and the background agents that write briefs cannot
    drift onto different backends — one LLM_BACKEND flag moves all of them.

    `background=True` selects the cheaper model. Background work is bounded and
    well-specified — survey these sources, compose this object — and there is a
    lot more of it than there is chat.
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
    return OpenAIModel(
        model_id=settings.GROQ_BACKGROUND_MODEL if background else settings.GROQ_MODEL,
        client_args={
            "api_key": settings.GROQ_API_KEY,
            "base_url": "https://api.groq.com/openai/v1",
        },
        # A structured report of eight gaps is a lot of tokens in one response,
        # and running out mid-object fails the whole run with
        # "unrecoverable state due to max_tokens limit".
        params={"max_tokens": settings.MAX_OUTPUT_TOKENS},
    )


_RETRY = ModelRetryStrategy(max_attempts=3, initial_delay=2, max_delay=8)


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

    search_tool, captured = make_search_tool(workspace_id, chroma_client, allowed_sources=allowed_sources)
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
    hooks = []
    grant_session = None
    refusals: list = []
    if grants:
        grant_session = GrantSession().open(grants)
        limit = max_grant_tools if max_grant_tools is not None else settings.MAX_GRANT_TOOLS_PER_TURN
        tools.extend(select_relevant(grant_session.tools, question, limit))
        narration.update(grant_session.narration)
        gate = grant_session.gate(on_refusal=lambda name, g: refusals.append({"tool": name, "grant": g}))
        hooks.append(gate)

    kwargs = dict(
        model=_build_model(),
        tools=tools,
        system_prompt=SENSEI_SYSTEM_PROMPT,
        retry_strategy=_RETRY,
    )
    if hooks:
        kwargs["hooks"] = hooks
    if session_manager is not None:
        kwargs["session_manager"] = session_manager

    col = Colleague(
        agent=Agent(**kwargs),
        citations=captured,
        artifacts=produced,
        narration=narration,
        refusals=refusals,
        unavailable=grant_session.failed if grant_session else [],
    )
    col._grants = grant_session
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
