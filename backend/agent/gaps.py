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

Report absences, not contents. For each, say what made you notice it — a
reference that goes nowhere, a component with no owner, a question the sources
cannot answer. Do not invent gaps to fill a quota, and do not list something as
missing without checking for it first."""

_COMPOSE = """You turn a documentation survey into a structured report.

Rules:
- Only include gaps the survey actually evidenced. No speculation.
- `can_draft` is true only when the indexed sources plainly contain the raw
  material — CI config and a Dockerfile can become a deployment doc; nothing in
  the index can become an incident runbook that was never written.
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
  rather than inventing a plausible one."""


def _agent(system_prompt: str, tools: list | None = None) -> Agent:
    return Agent(
        model=_build_model(),
        tools=tools or [],
        system_prompt=system_prompt,
        retry_strategy=ModelRetryStrategy(max_attempts=3, initial_delay=2, max_delay=8),
    )


# ── Audit ─────────────────────────────────────────────────────────────────────

async def audit_project(workspace_id: str, chroma_client) -> GapReport:
    search_tool, _ = make_search_tool(
        workspace_id, chroma_client, n_results=4, passage_chars=450, budget=4,
    )
    inventory_tool = make_inventory_tool(workspace_id, chroma_client)

    builder = GraphBuilder()
    builder.add_node(_agent(_SURVEY, [inventory_tool, search_tool]), node_id="survey")
    builder.set_entry_point("survey")
    builder.set_max_node_executions(3)
    builder.set_execution_timeout(300)
    builder.set_node_timeout(240)
    graph = builder.build()

    result = await graph.invoke_async(
        "Audit this project's documentation and report what is missing."
    )
    node = result.results.get("survey")
    survey = str(node.result) if node is not None else ""

    composer = _agent(_COMPOSE)
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
            return

    await db.gap_reports.update_one(
        {"workspace_id": workspace_id},
        {"$set": {"status": "scanning", "updated_at": now, "error_message": None},
         "$setOnInsert": {"_id": uuid4().hex, "created_at": now}},
        upsert=True,
    )

    try:
        report = await audit_project(workspace_id, chroma_client)
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
        await db.gap_reports.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"status": "error", "error_message": str(exc)[:400],
                      "updated_at": datetime.now(timezone.utc)}},
        )
        print(f"[gaps] audit failed for {workspace_id}: {exc}")


# ── Drafting — closing the gap ────────────────────────────────────────────────

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
        writer = _agent(_DRAFT, [search_tool])
        draft = await writer.structured_output_async(
            DraftDocument,
            f"Draft this missing document: {gap['title']}\n\n"
            f"Why it is needed: {gap['detail']}\n"
            f"Build it from these indexed sources: {', '.join(gap.get('draft_from') or []) or 'whatever you can find'}",
        )
        await db.drafts.update_one(
            {"workspace_id": workspace_id, "gap_id": gap_id},
            {"$set": {"status": "ready", "draft": draft.model_dump(),
                      "updated_at": datetime.now(timezone.utc), "error_message": None}},
        )
        print(f"[gaps] drafted '{draft.title}'")
    except Exception as exc:
        await db.drafts.update_one(
            {"workspace_id": workspace_id, "gap_id": gap_id},
            {"$set": {"status": "error", "error_message": str(exc)[:400],
                      "updated_at": datetime.now(timezone.utc)}},
        )
        print(f"[gaps] draft failed: {exc}")
