"""
The gap hunter — the agent auditing its own knowledge for what is absent.

Every knowledge tool tells you what it knows. The useful question in a real
project is the other one: what did nobody write down? Unowned services,
deployment steps that live only in someone's head, a decision log the PRD
references but which was never connected.

Finding the gap is half of it. The other half is that the agent can usually
close it — the deployment steps are latent in the CI config and the Dockerfile,
they were just never written as prose. So a gap carries a `can_draft` flag, and
the owner can ask for a draft. That is the decision this puts to a human.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from strands import Agent, ModelRetryStrategy
from strands.multiagent import GraphBuilder

from agent.agent import _build_model
from agent.tools import make_inventory_tool, make_search_tool
from agent import usage
from core.config import settings
from core.errors import humanise, refresh_error

RESCAN_DEBOUNCE = timedelta(minutes=10)


# ── The artifact ──────────────────────────────────────────────────────────────

class Gap(BaseModel):
    title: str = Field(description="The missing thing, named in a few words")
    kind: Literal["missing_document", "unowned_area", "dangling_reference", "thin_coverage"]
    detail: str = Field(description="What is missing and why it would matter to someone working here")
    evidence: list[str] = Field(
        default_factory=list,
        description="Source labels that imply this gap — what made you notice the absence",
    )
    severity: Literal["high", "medium", "low"]
    can_draft: bool = Field(description="True only if the indexed sources contain enough to write this")
    draft_from: list[str] = Field(
        default_factory=list,
        description="Which indexed sources a draft would be built from. Empty when can_draft is false.",
    )


class GapReport(BaseModel):
    summary: str = Field(description="One or two sentences on the overall state of this project's documentation")
    gaps: list[Gap] = Field(description="Up to 8, most consequential first")


class DraftDocument(BaseModel):
    title: str
    body_markdown: str = Field(description="The document itself, in markdown, ready to paste into a wiki")
    sources_used: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(
        default_factory=list,
        description="Anything inferred rather than found. Be explicit — a reader must know what to verify.",
    )


# ── Prompts ───────────────────────────────────────────────────────────────────

_SURVEY = """You are surveying a project's knowledge base to find what is MISSING.

Call `list_project_knowledge` first to see what exists. Then use
`search_project_docs` to test for things a working team needs. Look for:

- Documents that should exist and do not: how to deploy, how to run locally,
  how to get access, incident/runbook procedures, onboarding guides, decision
  records.
- Areas with no named owner. If a service, component or connector is described
  but nobody is recorded as responsible for it, that is a gap.
- Dangling references: a document mentions another document, board or system
  that is not in any indexed source.
- Thin coverage: a repository or space that is connected but holds almost
  nothing readable.

Before you call something missing, SEARCH FOR IT. The inventory tells you which
documents exist, not what is inside them — a README may well contain the local
setup steps you are about to report as absent. A gap you did not search for is a
guess, and a wrong one costs the reader more than saying nothing.

For each real absence, say what made you notice it — a reference that goes
nowhere, a component with no owner, a question the sources cannot answer.

Also note, for each, what raw material the sources DO hold that bears on it. A
Dockerfile and a CI workflow are most of a deployment document; a commit history
and a collaborator list are most of an ownership map. Someone downstream decides
whether that is enough to write from, so give them the evidence either way.

Report absences, not contents. Do not invent gaps to fill a quota."""

_COMPOSE = """You turn a documentation survey into a structured report.

Rules:
- Only include gaps the survey actually evidenced. No speculation.
- `can_draft` asks one question: could a careful writer produce a genuinely
  useful first draft from what the sources hold? Be willing here. A Dockerfile,
  a compose file and a CI workflow are most of a deployment document. A commit
  history and a collaborator list are most of an ownership map. Config and
  settings files are most of a local-run guide. The draft will be reviewed by a
  human before it is published, so a useful-but-incomplete draft beats refusing.

  Say false only when the sources hold essentially nothing on the subject — an
  incident runbook cannot be written from documentation that never mentions
  incidents. When false, `draft_from` is empty.
- `severity` is about consequence to someone doing the work, not tidiness.
  Nobody able to deploy is high. A missing README on a scratch repo is low.
- `evidence` keeps the source labels the survey named."""

_DRAFT = """You draft the missing document a project needs, from what its own
sources already contain.

Rules:
- Build only from what you find with `search_project_docs`. Search before you
  write.
- Where you infer rather than find, say so in `assumptions`. A reader must know
  exactly which lines to verify before trusting them.
- Write the document someone would actually use: concrete steps, real file and
  command names taken from the sources, no placeholder prose.
- If the sources genuinely do not support the document, say so in the body
  rather than inventing a plausible one.

Finish with exactly these two sections, in this order:

## Sources
- one bullet per indexed source you drew on

## Assumptions
- one bullet per thing you inferred rather than found; write "None" if there were none"""


def _agent(system_prompt: str, tools: list | None = None, background: bool = True) -> Agent:
    return Agent(
        model=_build_model(background=background),
        tools=tools or [],
        system_prompt=system_prompt,
        # Background work can afford to wait out a per-minute limit; a person
        # in chat cannot, which is why the chat agent retries less patiently.
        retry_strategy=ModelRetryStrategy(max_attempts=5, initial_delay=6, max_delay=45),
    )


# ── Audit ─────────────────────────────────────────────────────────────────────

async def audit_project(workspace_id: str, chroma_client, db=None) -> GapReport:
    search_tool, _ = make_search_tool(
        workspace_id, chroma_client, n_results=5, passage_chars=500, budget=6,
    )
    inventory_tool = make_inventory_tool(workspace_id, chroma_client)

    builder = GraphBuilder()
    builder.add_node(_agent(_SURVEY, [inventory_tool, search_tool]), node_id="survey")
    builder.set_entry_point("survey")
    builder.set_max_node_executions(3)
    builder.set_execution_timeout(300)
    builder.set_node_timeout(240)
    graph = builder.build()

    # The survey sometimes ends on its tool calls without writing anything up.
    # Composing from that yields a confident, empty report — a failure shaped
    # exactly like a clean bill of health, which is the worst way for this
    # feature to break. Check the survey actually said something.
    MIN_SURVEY = 400
    survey = ""
    for attempt in (1, 2):
        result = await graph.invoke_async(
            "Audit this project's documentation and report what is missing."
        )
        if db is not None:
            await usage.record(db, workspace_id, "gaps.survey",
                               getattr(result, "accumulated_usage", None),
                               settings.GROQ_BACKGROUND_MODEL)
        node = result.results.get("survey")
        survey = str(node.result).strip() if node is not None else ""
        if len(survey) >= MIN_SURVEY:
            break
        print(f"[gaps] survey returned {len(survey)} chars on attempt {attempt} — retrying")

    if len(survey) < MIN_SURVEY:
        raise RuntimeError(
            "The audit could not finish — the survey step returned nothing usable "
            "twice over. Try again shortly."
        )

    composer = _agent(_COMPOSE, background=False)
    return await composer.structured_output_async(
        GapReport, f"Survey findings:\n\n{survey}"
    )


async def scan_gaps(db, chroma_client, workspace_id: str, force: bool = False) -> None:
    """
    Audit a project and store the report.

    Runs unprompted after ingestion settles, debounced — a workspace with seven
    sources should not trigger seven audits.
    """
    now = datetime.now(timezone.utc)
    existing = await db.gap_reports.find_one({"workspace_id": workspace_id})

    if not force and existing:
        last = existing.get("updated_at")
        if last is not None:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if now - last < RESCAN_DEBOUNCE and existing.get("status") != "error":
                return
        if existing.get("status") == "scanning":
            # A run that died with the process leaves "scanning" behind; do not
            # let a ghost block every future audit.
            started = existing.get("updated_at")
            if started is not None and started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if started is not None and now - started < timedelta(minutes=15):
                return

    await db.gap_reports.update_one(
        {"workspace_id": workspace_id},
        {"$set": {"status": "scanning", "updated_at": now, "error_message": None},
         "$setOnInsert": {"_id": uuid4().hex, "created_at": now}},
        upsert=True,
    )

    try:
        from agent.agent import retry_on_quota
        report = await retry_on_quota(audit_project, workspace_id, chroma_client, db)
        gaps = []
        for g in report.gaps:
            d = g.model_dump()
            d["id"] = uuid4().hex[:12]      # addressable, so a draft can be requested
            gaps.append(d)
        await db.gap_reports.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"status": "ready", "summary": report.summary, "gaps": gaps,
                      "updated_at": datetime.now(timezone.utc), "error_message": None}},
        )
        print(f"[gaps] {len(gaps)} gap(s) found in workspace {workspace_id}")
    except Exception as exc:
        current = await db.gap_reports.find_one({"workspace_id": workspace_id})
        has_report = bool((current or {}).get("gaps"))
        await db.gap_reports.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"status": "ready" if has_report else "error",
                      "error_message": None if has_report else humanise(exc),
                      "refresh_error": refresh_error(exc) if has_report else None,
                      "updated_at": datetime.now(timezone.utc)}},
        )
        print(f"[gaps] audit failed for {workspace_id}: {exc}")


# ── Drafting — closing the gap ────────────────────────────────────────────────

def _parse_draft(text: str, fallback_title: str) -> DraftDocument:
    """
    Split a drafted markdown document into body, sources and assumptions.

    The writer is asked to end with `## Sources` and `## Assumptions`. Both are
    optional here: a draft missing them is still a useful draft, and losing the
    document because a heading was spelled differently would be absurd.
    """
    import re

    def take(heading: str) -> list[str]:
        m = re.search(rf"^#+\s*{heading}\s*$(.*?)(?=^#+\s|\Z)", text,
                      re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if not m:
            return []
        items = [
            re.sub(r"^[-*]\s*", "", ln).strip()
            for ln in m.group(1).strip().splitlines()
            if ln.strip().startswith(("-", "*"))
        ]
        return [i for i in items if i and i.lower() not in {"none", "n/a"}]

    sources = take("Sources")
    assumptions = take("Assumptions")

    # Body is everything before the trailing sections.
    body = text
    cut = re.search(r"^#+\s*Sources\s*$", text, re.IGNORECASE | re.MULTILINE)
    if cut:
        body = text[: cut.start()].rstrip()

    # Look for the title outside fenced code. A guide that shows shell output
    # will contain lines starting with '#', and the first one won it — the last
    # draft was titled "backend   | 0.0.0.0:8000->8000/tcp".
    uncoded = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    title = fallback_title
    heading = re.search(r"^#\s+(.+)$", uncoded, re.MULTILINE)
    if heading:
        title = heading.group(1).strip()
    else:
        # Many drafts open with a bold line instead of a heading.
        bold = re.search(r"^\*\*(.+?)\*\*\s*$", uncoded.strip(), re.MULTILINE)
        if bold:
            title = bold.group(1).strip()
    return DraftDocument(
        title=title,
        body_markdown=body.strip(),
        sources_used=sources,
        assumptions=assumptions,
    )



async def draft_for_gap(db, chroma_client, workspace_id: str, gap_id: str) -> None:
    """Write the missing document, from the sources the gap named."""
    now = datetime.now(timezone.utc)
    report = await db.gap_reports.find_one({"workspace_id": workspace_id})
    gap = next((g for g in (report or {}).get("gaps", []) if g.get("id") == gap_id), None)
    if not gap:
        return

    await db.drafts.update_one(
        {"workspace_id": workspace_id, "gap_id": gap_id},
        {"$set": {"status": "drafting", "updated_at": now, "error_message": None,
                  "gap_title": gap.get("title")},
         "$setOnInsert": {"_id": uuid4().hex, "created_at": now}},
        upsert=True,
    )

    try:
        search_tool, _ = make_search_tool(
            workspace_id, chroma_client, n_results=5, passage_chars=700, budget=3,
        )

        # Two steps, and they cannot be collapsed into one. Asking an agent that
        # holds tools for structured output sets tool_choice="none" while the
        # model still wants to search, and the provider rejects the call
        # outright: "Tool choice is none, but model called a tool". So the
        # researcher gathers with tools, and a second agent with none shapes the
        # result.
        writer = _agent(_DRAFT, [search_tool])
        written = await writer.invoke_async(
            f"Draft this missing document: {gap['title']}\n\n"
            f"Why it is needed: {gap['detail']}\n"
            f"Build it from these indexed sources: "
            f"{', '.join(gap.get('draft_from') or []) or 'whatever you can find'}"
        )
        await usage.record(db, workspace_id, "gaps.draft.write",
                           getattr(written, "accumulated_usage", None),
                           settings.GROQ_BACKGROUND_MODEL)

        # No second model call. The draft is already markdown, and pushing a long
        # document through a JSON schema only added a way to fail — the shaper
        # returned an empty generation and took the whole draft down with it.
        # The writer is asked for two trailing sections; parse those out.
        draft = _parse_draft(str(written), gap["title"])
        await db.drafts.update_one(
            {"workspace_id": workspace_id, "gap_id": gap_id},
            {"$set": {"status": "ready", "draft": draft.model_dump(),
                      "updated_at": datetime.now(timezone.utc), "error_message": None}},
        )
        print(f"[gaps] drafted '{draft.title}'")
    except Exception as exc:
        await db.drafts.update_one(
            {"workspace_id": workspace_id, "gap_id": gap_id},
            {"$set": {"status": "error", "error_message": humanise(exc),
                      "updated_at": datetime.now(timezone.utc)}},
        )
        print(f"[gaps] draft failed: {exc}")
