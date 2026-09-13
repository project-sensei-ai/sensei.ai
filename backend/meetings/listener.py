"""
The colleague in the meeting.

A teammate in a call does three things a transcript bot does not: answers
when addressed, stays quiet the rest of the time, and — rarely, and only when
sure — says "actually, that's not right, the runbook says X". This module is
that judgement, applied to one utterance at a time.

Three outcomes, and the default is silence:

    answer      — someone said its name and asked something. Always respond,
                  even if the answer is "the sources don't say".
    correction  — nobody asked, but a person stated a project fact the
                  sources contradict. Speak ONLY if a typed verdict says the
                  claim is contradicted, with confidence ≥ 0.8, AND a citation
                  exists. All three, or nothing.
    silent      — everything else, which is nearly everything.

The correction gate is deliberately strict. A colleague who corrects people
on a hunch is asked to leave the call. One who corrects with the page open in
front of them is the one you wanted in the room.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from strands import Agent, ModelRetryStrategy

from agent.agent import _build_model
from agent.tools import make_inventory_tool, make_search_tool
from channels.router import best_match_score

AGENT_NAMES = ("sensei",)
CORRECTION_CONFIDENCE = 0.8
# Below this, the utterance is not even about the project — no model call.
CLAIM_RELEVANCE_FLOOR = 0.35

# Addressed means spoken TO, not ABOUT. The product shares its name with the
# agent, so "the vector store for Sensei is Pinecone" is a claim about the
# project, not a question to it. Only a leading or trailing vocative counts:
# "Sensei, what…", "hey Sensei…", "…right, Sensei?"
_ADDRESSED = re.compile(
    r"(^\s*(hey|hi|ok|okay|hello|so|right|um|uh)?[\s,]*sensei\b[\s,:!?-]*)|(\bsensei[\s,!?.]*$)",
    re.IGNORECASE,
)
# Assertions worth checking look like statements of fact about the project,
# not opinions, questions, or chatter.
_ASSERTION = re.compile(
    r"\b(is|are|was|were|uses|use|runs|run|deploys?|deployed|owns?|owned|lives?|handles?|"
    r"stores?|calls?|talks? to|written in|built (on|with)|hosted|the (owner|default|limit|"
    r"timeout|port|region|bucket|branch) (is|was))\b",
    re.IGNORECASE,
)
_HEDGE = re.compile(r"\b(i think|maybe|probably|not sure|might|could be|i guess|if i recall|\?)", re.IGNORECASE)


class ClaimVerdict(BaseModel):
    """What the sources say about a thing somebody just asserted."""
    is_factual_claim: bool = Field(description="True if the utterance asserts a checkable fact about this project")
    claim: str = Field(default="", description="The claim, restated in one sentence")
    supported: bool = Field(default=False, description="The sources agree with the claim")
    contradicted: bool = Field(default=False, description="The sources clearly say something different")
    confidence: float = Field(default=0.0, ge=0, le=1, description="How sure you are, 0–1. Be honest; 0.9+ only when a source states the opposite outright")
    correction: str = Field(default="", description="If contradicted: one or two spoken sentences correcting it, naming the source. Otherwise empty")
    evidence: str = Field(default="", description="The passage that decides it, quoted briefly")


@dataclass
class Reply:
    kind: str                     # answer | correction | silent
    text: str = ""
    citations: list = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""
    trigger: str = ""
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_doc(self) -> dict:
        return {"kind": self.kind, "text": self.text, "citations": self.citations,
                "confidence": self.confidence, "reason": self.reason,
                "trigger": self.trigger, "at": self.at}


def is_addressed(text: str) -> bool:
    return bool(_ADDRESSED.search(text or ""))


def strip_address(text: str) -> str:
    return _ADDRESSED.sub("", text or "").strip(" ,:-?") or (text or "")


def looks_like_an_assertion(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 20 or t.endswith("?"):
        return False
    if _HEDGE.search(t):
        return False
    return bool(_ASSERTION.search(t))


_ANSWER_PROMPT = """You are Sensei, a colleague sitting in this meeting. Someone just said your name
and asked you something. Answer the way a person would out loud: two to four
sentences, no headings, no bullet lists, no markdown. Lead with the answer.
Name the source in plain words ("the architecture doc says…", "per PROJ-412").
If the project's sources do not cover it, say so in one sentence and stop —
never guess in a meeting. Use `search_project_docs` once; use
`list_project_knowledge` if they ask what you know about.

Recent conversation, for context:
{context}
"""

_VERDICT_PROMPT = """You check claims people make in meetings against a project's own documentation.
You are given a claim and passages retrieved from the sources. Decide, strictly:

- `contradicted` is true ONLY if a passage states something that cannot both be
  true with the claim. Absence of evidence is NOT contradiction.
- `confidence` reflects how directly the passage speaks to the claim. If you
  would have to infer, stay under 0.7.
- `correction` is what you would say out loud in the room: short, polite,
  specific, naming the document. Empty unless contradicted.

Be conservative. A wrong correction in front of a team costs far more than a
missed one."""


def _agent(system_prompt: str, tools: list | None = None) -> Agent:
    return Agent(
        model=_build_model(background=True),
        tools=tools or [],
        system_prompt=system_prompt,
        retry_strategy=ModelRetryStrategy(max_attempts=2, initial_delay=2, max_delay=6),
        callback_handler=None,
    )


async def answer_when_addressed(workspace_id: str, chroma_client, text: str, context: str,
                                allowed_sources: list[str] | None = None) -> Reply:
    search_tool, captured = make_search_tool(
        workspace_id, chroma_client, n_results=5, passage_chars=500, budget=2,
        allowed_sources=allowed_sources,
    )
    inventory = make_inventory_tool(workspace_id, chroma_client, allowed_sources)
    agent = _agent(_ANSWER_PROMPT.format(context=context or "(none)"), [search_tool, inventory])
    result = await agent.invoke_async(strip_address(text) or text)
    return Reply(kind="answer", text=str(result).strip(), citations=list(captured),
                 confidence=1.0 if captured else 0.5, reason="addressed by name", trigger=text)


async def check_claim(workspace_id: str, chroma_client, text: str,
                      allowed_sources: list[str] | None = None) -> Reply:
    """The correction gate. Cheap checks first; the model only runs when the
    utterance is a project-shaped assertion the sources might speak to."""
    if not looks_like_an_assertion(text):
        return Reply(kind="silent", reason="not a factual assertion", trigger=text)

    from db.chroma import get_workspace_collection
    collection = get_workspace_collection(chroma_client, workspace_id)
    score = best_match_score(text, collection)
    if score < CLAIM_RELEVANCE_FLOOR:
        return Reply(kind="silent", reason=f"not about this project (best match {score:.2f})",
                     trigger=text, confidence=score)

    # Retrieve once, then judge with a typed verdict — no free-form prose to parse.
    search_tool, captured = make_search_tool(
        workspace_id, chroma_client, n_results=5, passage_chars=600, budget=1,
        allowed_sources=allowed_sources,
    )
    passages = search_tool(query=text)
    if not captured:
        return Reply(kind="silent", reason="nothing retrievable to check it against", trigger=text)

    judge = _agent(_VERDICT_PROMPT)
    verdict = await judge.structured_output_async(
        ClaimVerdict, f"Claim (said in a meeting): {text}\n\nPassages from the project's sources:\n\n{passages}"
    )
    if not verdict.is_factual_claim:
        return Reply(kind="silent", reason="the model did not read it as a checkable claim", trigger=text)
    if not verdict.contradicted:
        return Reply(kind="silent",
                     reason="supported by the sources" if verdict.supported else "sources neither confirm nor contradict",
                     trigger=text, confidence=verdict.confidence)
    if verdict.confidence < CORRECTION_CONFIDENCE:
        return Reply(kind="silent",
                     reason=f"contradiction suspected but confidence {verdict.confidence:.2f} < {CORRECTION_CONFIDENCE}",
                     trigger=text, confidence=verdict.confidence)
    if not verdict.correction.strip():
        return Reply(kind="silent", reason="contradicted but no correction was produced", trigger=text,
                     confidence=verdict.confidence)
    return Reply(kind="correction", text=verdict.correction.strip(), citations=list(captured),
                 confidence=verdict.confidence,
                 reason=f"sources contradict it: {verdict.evidence[:160]}", trigger=text)


async def consider(workspace_id: str, chroma_client, text: str, context: str,
                   allowed_sources: list[str] | None = None) -> Reply:
    """One utterance in. One decision out, and it is usually silence."""
    if is_addressed(text):
        return await answer_when_addressed(workspace_id, chroma_client, text, context, allowed_sources)
    return await check_claim(workspace_id, chroma_client, text, allowed_sources)


# ── After the meeting ─────────────────────────────────────────────────────────

class MeetingSummary(BaseModel):
    summary: str = Field(description="3-6 sentences on what the meeting covered")
    decisions: list[str] = Field(default_factory=list, description="Decisions actually made, one line each")
    action_items: list[str] = Field(default_factory=list, description="Who does what, as stated; empty if none")
    open_questions: list[str] = Field(default_factory=list, description="Questions raised and not resolved")


async def summarise(title: str, transcript: list[dict]) -> MeetingSummary:
    lines = "\n".join(f"{u.get('speaker', '?')}: {u.get('text', '')}" for u in transcript)
    agent = _agent(
        "You write short, factual meeting notes from a transcript. Only record what "
        "was said. Attribute decisions and action items to the people who made them. "
        "Never invent a decision that was not explicitly agreed."
    )
    return await agent.structured_output_async(
        MeetingSummary, f"Meeting: {title}\n\nTranscript:\n{lines[:24000]}"
    )


def transcript_as_document(title: str, held_at: str, transcript: list[dict], summary: MeetingSummary | None) -> str:
    parts = [f"# Meeting: {title}", f"Held: {held_at[:16].replace('T', ' ')} UTC", ""]
    if summary:
        parts += ["## Summary", summary.summary, ""]
        if summary.decisions:
            parts += ["## Decisions"] + [f"- {d}" for d in summary.decisions] + [""]
        if summary.action_items:
            parts += ["## Action items"] + [f"- {a}" for a in summary.action_items] + [""]
        if summary.open_questions:
            parts += ["## Open questions"] + [f"- {q}" for q in summary.open_questions] + [""]
    parts += ["## Transcript"] + [f"{u.get('speaker', '?')}: {u.get('text', '')}" for u in transcript]
    return "\n".join(parts)
