"""
The self-interview.

A new hire's first week ends with a question nobody asks out loud: are they
actually ready? Sensei asks it of itself. Once a project's sources have
landed, it writes the eight questions a new joiner would ask *this* project,
tries to answer each from the sources alone, and grades itself honestly.

The score is the honest half of the product: "ready for 6 of 8" says more
than "connected 3 sources". The two it could not answer go straight into the
answer ledger, attributed to Sensei itself — an owner answers each once and
the gap is closed for everyone, permanently.

Cheap by construction: one call to write the questions, plain retrieval per
question (no model), one call to grade all eight against what was retrieved.
"""
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from agent.schemas import Lenient
from strands import Agent, ModelRetryStrategy

from agent import usage
from agent.agent import _build_model, retry_on_quota
from agent.tools import make_inventory_tool, make_search_tool
from core.config import settings
from core.errors import humanise, refresh_error, reworded, stored_refresh_error
from core.formatting import plain_answer

QUESTIONS = 8
RERUN_AFTER = timedelta(minutes=20)

SELF = {"id": "sensei", "name": "Sensei (self-check)", "email": None}


class JoinerQuestion(Lenient):
    question: str = Field(description="One specific question a new joiner to THIS project would ask in week one")
    why: str = Field(description="Why they would need it, in a few words")


class QuestionSet(Lenient):
    questions: list[JoinerQuestion] = Field(description=f"Exactly {QUESTIONS} questions, each about a different area")


class Grade(Lenient):
    question: str
    answerable: bool = Field(description="True only if the passages actually contain the answer")
    answer: str = Field(default="", description="The answer in one or two sentences, if answerable; else empty")
    source: str = Field(default="", description="The source label that supports it, if answerable")


class ReadinessGrades(Lenient):
    grades: list[Grade]


_ASK = """You are about to start work as a new engineer on this project. From the
inventory of what has been shared with you, write the {n} questions you would
most need answered in your first week — the ones that decide whether you can
actually do the job: how it is built, how it ships, who owns what, where
things run, what the limits are, what to do when something breaks, what is in
flight. Be specific to THIS project; name its components and people where the
inventory shows them. Ask the way a person asks a colleague — "who do I talk
to about the routing worker", "what's the deploy window" — not by file path or
line. One thing per question — never "…, and …" — so each can be answered or
not. Cover {n} different areas; no two questions alike."""

_GRADE = """You are grading whether a project's own sources can answer each
question below. For each, you are given the passages retrieved for it. Mark
`answerable` true when the passages contain the information the question
needs, even if phrased differently or spread across two passages, and even if
a minor secondary detail is missing; mark it false when the core answer would
have to come from inference or general knowledge.
When true, give the answer briefly and name the source label. A wrong "yes"
hides a gap the team needs to see; a wrong "no" sends a person to close a gap
that is not there. Return one grade per question, in the same order, with the
question text copied exactly."""


def _agent(prompt: str, tools: list | None = None) -> Agent:
    return Agent(model=_build_model(background=True), tools=tools or [], system_prompt=prompt,
                 retry_strategy=ModelRetryStrategy(max_attempts=5, initial_delay=6, max_delay=45),
                 callback_handler=None)


async def _write_questions(workspace_id: str, chroma_client, project_name: str) -> QuestionSet:
    inventory = make_inventory_tool(workspace_id, chroma_client)()
    agent = _agent(_ASK.format(n=QUESTIONS))
    return await agent.structured_output_async(
        QuestionSet, f"Project: {project_name}\n\nWhat has been shared with you:\n{inventory[:6000]}"
    )


async def _grade(workspace_id: str, chroma_client, questions: list[JoinerQuestion]) -> ReadinessGrades:
    """Retrieve for every question, then grade in batches of four so each
    question gets enough of its passages in front of the model."""
    grades: list[Grade] = []
    for start in range(0, len(questions), 4):
        blocks = []
        for q in questions[start:start + 4]:
            search, _ = make_search_tool(workspace_id, chroma_client, n_results=6, passage_chars=650, budget=1)
            passages = search(query=q.question)
            blocks.append(f"### Question: {q.question}\n{passages[:4200]}")
        agent = _agent(_GRADE)
        part = await agent.structured_output_async(ReadinessGrades, "\n\n".join(blocks))
        grades.extend(part.grades)
    return ReadinessGrades(grades=grades)


async def run_readiness(db, chroma_client, workspace_id: str, force: bool = False) -> None:
    """Interview itself, store the report, and put what it could not answer in the ledger."""
    from answers import store as answer_store

    existing = await db.readiness.find_one({"workspace_id": workspace_id})
    now = datetime.now(timezone.utc)
    if existing and not force:
        last = existing.get("updated_at")
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if existing.get("status") == "running" and last and now - last < timedelta(minutes=10):
            return
        if existing.get("status") == "ready" and last and now - last < RERUN_AFTER:
            return

    workspace = await db.workspaces.find_one({"_id": workspace_id})
    name = (workspace or {}).get("name", "this project")
    await db.readiness.update_one(
        {"workspace_id": workspace_id},
        {"$set": {"status": "running", "updated_at": now, "error_message": None},
         "$setOnInsert": {"_id": uuid4().hex, "created_at": now}},
        upsert=True,
    )
    try:
        qs = await retry_on_quota(_write_questions, workspace_id, chroma_client, name)
        questions = qs.questions[:QUESTIONS]
        graded = await retry_on_quota(_grade, workspace_id, chroma_client, questions)
        by_q = {g.question.strip().lower(): g for g in graded.grades}
        items = []
        for q in questions:
            g = by_q.get(q.question.strip().lower()) or next(
                (x for x in graded.grades if x.question[:40].lower() == q.question[:40].lower()), None)
            items.append({
                "question": q.question, "why": q.why,
                "answerable": bool(g and g.answerable),
                "answer": plain_answer((g.answer if g else "") or ""),
                "source": clean_source(g.source if g else ""),
            })
        score = sum(1 for i in items if i["answerable"])

        # What it could not answer is the most useful output. Into the ledger,
        # as questions Sensei asked itself, so an owner can close them once.
        # Each interview replaces the previous one's open self-check questions;
        # the ones a person already answered stay, because they are knowledge.
        await db.unanswered.delete_many({"workspace_id": workspace_id, "asked_by_id": SELF["id"], "status": "open"})
        for i in items:
            if not i["answerable"]:
                await answer_store.record(db, workspace_id, i["question"], SELF, "self-check")

        await db.readiness.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"status": "ready", "score": score, "total": len(items), "items": items,
                      "updated_at": datetime.now(timezone.utc), "error_message": None,
                      "refresh_error": None}},
        )
        await usage.record(db, workspace_id, "readiness", None, settings.GROQ_BACKGROUND_MODEL)
        print(f"[readiness] {name}: ready for {score} of {len(items)}")
    except Exception as exc:
        keep = bool((existing or {}).get("items"))
        await db.readiness.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"status": "ready" if keep else "error",
                      "error_message": None if keep else humanise(exc),
                      "refresh_error": refresh_error(exc) if keep else None,
                      "updated_at": datetime.now(timezone.utc)}},
        )
        print(f"[readiness] failed for {workspace_id}: {exc}")


_MARKER = re.compile(r"\[\s*\^?\d+(?:\s*[,–-]\s*\d+)*\s*\]|【[^】]*】")


def clean_source(source: str | None) -> str:
    """ "[5] Confluence: SD – Apollo — Deployment runbook" reads as the name alone."""
    text = _MARKER.sub("", source or "")
    text = re.sub(r"^\s*\[([^\[\]]+)\]\s*$", r"\1", text.strip())   # a label wrapped whole in brackets
    return re.sub(r"\s{2,}", " ", text).strip(" ,;")


def serialize(doc: dict | None) -> dict | None:
    if not doc:
        return None
    from db.models import _iso
    return {
        "status": doc.get("status"),
        "score": doc.get("score", 0),
        "total": doc.get("total", 0),
        # Reports written before sources were cleaned still carry the markers.
        "items": [{**i, "source": clean_source(i.get("source"))} for i in doc.get("items", [])],
        "error_message": reworded(doc.get("error_message")),
        "refresh_error": stored_refresh_error(doc.get("refresh_error")),
        "updated_at": _iso(doc.get("updated_at")),
    }
