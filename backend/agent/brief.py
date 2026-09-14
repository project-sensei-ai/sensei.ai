"""
The onboarding brief — the agent's first piece of unprompted work.

When an owner adds someone to a project, nothing asks the agent anything. It
goes and researches the project for that person and writes them a brief, which
is waiting when they first log in.

Shape:

    scout ──► project_facts ──► people_and_work ──► compose (typed)

The three research nodes are a Strands `Graph`: the scout inventories what the
workspace actually holds, then two researchers work over that inventory. The
composer is a separate structured-output call, so the result is a typed object
that renders as a page and can be diffed when the project changes — not prose.
"""
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from agent.schemas import Lenient
from strands import Agent
from strands.multiagent import GraphBuilder

from agent.agent import _build_model
from core.config import settings
from core.errors import humanise, refresh_error
from agent.tools import make_inventory_tool, make_search_tool
from agent import usage


# ── The artifact ──────────────────────────────────────────────────────────────

class ReadingItem(Lenient):
    title: str = Field(description="Document or page name, exactly as it is named in the sources")
    source: str = Field(description="Which source it lives in, e.g. 'Confluence: ENG' or 'README.md'")
    why: str = Field(description="One line on why this person should read it")


class PersonToMeet(Lenient):
    name: str = Field(description="Person's name or handle as it appears in the sources")
    why: str = Field(description="What they own or know that is relevant to this joiner")


class BriefSection(Lenient):
    heading: str
    body: str = Field(description="2-4 sentences. Only facts supported by the findings.")
    sources: list[str] = Field(default_factory=list, description="Source labels supporting this section")


class OnboardingBrief(Lenient):
    """A new joiner's orientation, assembled from the project's own sources."""
    headline: str = Field(description="One sentence: what this project is, in plain language")
    sections: list[BriefSection] = Field(description="3-5 sections: what it does, how it is built, how work flows, anything notable")
    reading_list: list[ReadingItem] = Field(default_factory=list, description="Up to 5, most useful first")
    people_to_meet: list[PersonToMeet] = Field(default_factory=list, description="Up to 5 people actually named in the sources")
    open_questions: list[str] = Field(
        default_factory=list,
        description="Things a new joiner would need that the sources do NOT answer. Be specific and honest.",
    )


# ── The graph ─────────────────────────────────────────────────────────────────

_SCOUT = """You are taking stock of a project's knowledge base for a new joiner.

Call `list_project_knowledge` once, then reply with AT MOST 10 short lines:
one per source, naming it and what it holds. No tables, no commentary, no
reading advice — later steps do that. Your output is passed to other agents, so
every extra line costs them context."""

_FACTS = """You are researching a project so a new joiner can be oriented.

Using the inventory you were given, search for: what the project does and who it
is for, how it is built (architecture, stack, major components), and how work
flows through it.

Report findings as short factual bullets. After each, name the source in square
brackets, e.g. [ARCHTECTRUE.md]. If something is not in the sources, say so
rather than filling the gap from general knowledge."""

_PEOPLE = """You are researching who does what on a project, for a new joiner.

Search for: who contributes, who owns which areas, recent activity, and any work
currently in flight. Prefer names and handles that actually appear in the
sources.

Report short factual bullets, each naming its source in square brackets. If
ownership is not recorded anywhere, say that plainly — it is useful to know."""

_COMPOSE = """You write onboarding briefs for people joining a software project.

You are given research findings gathered from that project's own sources. Turn
them into a brief for the named person.

Rules:
- Every claim must come from the findings. Never add knowledge of your own.
- Keep the source labels from the findings in each section's `sources`.
- `open_questions` is the honest part: list what a new joiner genuinely needs
  that the sources do not answer. An empty list is almost always wrong.
- Write to the person, plainly. No filler, no welcome-aboard padding."""


def _agent(system_prompt: str, tools: list | None = None) -> Agent:
    from strands import ModelRetryStrategy
    return Agent(
        model=_build_model(background=True),
        tools=tools or [],
        system_prompt=system_prompt,
        # Background work can afford to wait out a per-minute limit; a person
        # in chat cannot, which is why the chat agent retries less patiently.
        retry_strategy=ModelRetryStrategy(max_attempts=5, initial_delay=6, max_delay=45),
    )


async def research_project(workspace_id: str, chroma_client, db=None) -> str:
    """Run the research graph and return the combined findings as text."""
    def fresh_search():
        """A tool instance per node. The search budget and the seen-chunks set
        live in the factory closure, so sharing one instance across nodes means
        the first researcher spends the budget for everybody."""
        tool, _ = make_search_tool(
            workspace_id, chroma_client,
            n_results=4, passage_chars=450, budget=2,
        )
        return tool

    inventory_tool = make_inventory_tool(workspace_id, chroma_client)

    builder = GraphBuilder()
    builder.add_node(_agent(_SCOUT, [inventory_tool]), node_id="scout")
    builder.add_node(_agent(_FACTS, [fresh_search()]), node_id="project_facts")
    builder.add_node(_agent(_PEOPLE, [fresh_search()]), node_id="people_and_work")
    # Chained rather than fanned out. Running the researchers in parallel put two
    # simultaneous streams of tool-heavy calls through one API key; the provider
    # throttled, the retry backed off, and the node hit its timeout. Sequential
    # is slower and finishes.
    builder.add_edge("scout", "project_facts")
    builder.add_edge("project_facts", "people_and_work")
    builder.set_entry_point("scout")
    # The graph is acyclic, but bound it anyway: a background task that can run
    # forever is worse than one that fails.
    builder.set_max_node_executions(6)
    builder.set_execution_timeout(300)
    builder.set_node_timeout(180)
    graph = builder.build()

    result = await graph.invoke_async(
        "Take stock of this project and research it for someone about to join the team."
    )

    if db is not None:
        await usage.record(db, workspace_id, "brief.research",
                           getattr(result, "accumulated_usage", None),
                           settings.GROQ_BACKGROUND_MODEL)

    parts = []
    for node_id in ("project_facts", "people_and_work"):
        node = result.results.get(node_id)
        if node is not None:
            parts.append(f"## Findings — {node_id.replace('_', ' ')}\n{node.result}")
    return "\n\n".join(parts) if parts else ""


async def get_or_build_research(db, chroma_client, workspace_id: str) -> str:
    """
    Research findings for a project, reused across people.

    Researching a project costs three agents and a dozen tool calls. Composing
    one person's brief from findings costs a single call with no tools. Those
    two facts were previously welded together, so adding five teammates ran the
    same research five times to produce five nearly identical inputs.

    Findings are cached per workspace and invalidated by the corpus changing —
    `chunk_count` is a coarse fingerprint, but a source landing or being removed
    is exactly when the research is genuinely stale, and that always moves it.
    """
    from datetime import timedelta

    collection = None
    chunk_count = 0
    try:
        from db.chroma import get_workspace_collection
        collection = get_workspace_collection(chroma_client, workspace_id)
        chunk_count = collection.count()
    except Exception:
        pass

    cached = await db.research_cache.find_one({"workspace_id": workspace_id})
    if cached and cached.get("chunk_count") == chunk_count and cached.get("findings"):
        age_limit = timedelta(hours=settings.RESEARCH_TTL_HOURS)
        when = cached.get("updated_at")
        if when is not None:
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - when < age_limit:
                print(f"[brief] reusing research for {workspace_id} ({chunk_count} chunks)")
                return cached["findings"]

    findings = await research_project(workspace_id, chroma_client, db)
    await db.research_cache.update_one(
        {"workspace_id": workspace_id},
        {"$set": {"findings": findings, "chunk_count": chunk_count,
                  "updated_at": datetime.now(timezone.utc)},
         "$setOnInsert": {"_id": uuid4().hex}},
        upsert=True,
    )
    return findings


async def compose_brief(findings: str, person_name: str, project_name: str) -> OnboardingBrief:
    """Turn findings into the typed artifact."""
    composer = _agent(_COMPOSE)
    return await composer.structured_output_async(
        OnboardingBrief,
        f"Project: {project_name}\nJoiner: {person_name}\n\nFindings:\n\n{findings}",
    )


# ── Orchestration + storage ───────────────────────────────────────────────────

async def generate_brief(db, chroma_client, workspace_id: str, user_id: str) -> None:
    """
    Research the project and write this person's brief. Runs unprompted, as a
    background task, when an owner adds someone to a project.
    """
    now = datetime.now(timezone.utc)
    user = await db.users.find_one({"_id": user_id})
    workspace = await db.workspaces.find_one({"_id": workspace_id})
    if not user or not workspace:
        return

    person = user.get("name") or (user.get("email") or "").split("@")[0]

    await db.briefs.update_one(
        {"workspace_id": workspace_id, "user_id": user_id},
        {"$set": {"status": "generating", "updated_at": now, "error_message": None},
         "$setOnInsert": {"_id": uuid4().hex, "created_at": now,
                          "person_name": person, "person_email": user.get("email")}},
        upsert=True,
    )

    try:
        from agent.agent import retry_on_quota
        findings = await retry_on_quota(get_or_build_research, db, chroma_client, workspace_id)
        if not findings.strip():
            raise RuntimeError(
                "Nothing is indexed for this project yet, so there is nothing to brief on."
            )
        brief = await retry_on_quota(compose_brief, findings, person, workspace.get("name", "this project"))
        await usage.record(db, workspace_id, "brief.compose", None, settings.GROQ_BACKGROUND_MODEL)
        await db.briefs.update_one(
            {"workspace_id": workspace_id, "user_id": user_id},
            {"$set": {"status": "ready", "brief": brief.model_dump(),
                      "updated_at": datetime.now(timezone.utc), "error_message": None},
             "$unset": {"stale_reason": "", "stale_at": ""}},
        )
        print(f"[brief] wrote onboarding brief for {person} in {workspace.get('name')}")
    except Exception as exc:
        # A refresh that fails must not take a good brief off the page. Keep
        # the last one readable and say the refresh did not happen.
        current = await db.briefs.find_one({"workspace_id": workspace_id, "user_id": user_id})
        has_brief = bool((current or {}).get("brief"))
        await db.briefs.update_one(
            {"workspace_id": workspace_id, "user_id": user_id},
            {"$set": {"status": "ready" if has_brief else "error",
                      "error_message": None if has_brief else humanise(exc),
                      "refresh_error": refresh_error(exc) if has_brief else None,
                      "updated_at": datetime.now(timezone.utc)}},
        )
        print(f"[brief] failed for {person}: {exc}")
