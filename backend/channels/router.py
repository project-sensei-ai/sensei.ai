"""
Deciding whether the agent should say anything.

Once an agent can read every message in a channel, the interesting problem stops
being "can it answer" and becomes "should it". A bot that replies to everything
gets muted within a day, and a muted bot helps nobody.

So there are three outcomes, and two of them are silence:

    mentioned  — someone asked it directly. Always answer.
    proactive  — nobody asked, but a person posted a question the project's own
                 sources answer. This is the point of the product: they would
                 otherwise wait hours for the one colleague who knows.
    silent     — everything else, which is most of it.

Four gates, cheapest first, and the last one is the load-bearing one:

    1. shape      free. Is this even a question?
    2. relevance  free. Is it remotely about this project?
    3. answer     one agent call.
    4. citations  free. Did the answer cite anything?

Gate 4 exists because similarity scores do not discriminate. Measured against a
real 256-chunk corpus, "how does the ingestion pipeline work" — thoroughly
documented — scored 0.38, while "what is our AWS bill this month" — documented
nowhere — scored 0.49. Any threshold that admits the first admits the second.

What does discriminate is whether the agent could cite a source. It already
refuses honestly when the sources do not cover something, and a refusal carries
no citations. So the rule is simply: no citations, no post. The agent may think
out loud, but it only speaks in a channel when it can show its work.
"""
import re
from dataclasses import dataclass
from enum import Enum

from channels.base import IncomingMessage

# Only a coarse "is this about the project at all" gate, to avoid spending a
# model call on "when is the next all-hands". Deliberately low: the real
# judgement happens at gate 4, on whether the answer could cite anything.
RELEVANCE_FLOOR = 0.30
MIN_QUESTION_CHARS = 15

_QUESTION_OPENERS = re.compile(
    r"^\s*(who|what|where|when|why|how|which|is|are|does|do|did|can|could|should|"
    r"would|will|any(one|body)|has|have|was|were)\b",
    re.IGNORECASE,
)

# Social chatter. Kept narrow on purpose — an earlier version listed "weekend",
# which silenced "who is on call this weekend?", a perfectly real question.
# Over-filtering here is invisible; the agent simply never speaks and nobody
# knows why.
_NOT_FOR_US = re.compile(
    r"(\blunch\b|\bcoffee\b|\bbirthday\b|congrats|congratulations|"
    r"^\s*thanks|^\s*thank you|good morning|good night|\banyone free\b|"
    r"happy (friday|weekend|birthday))",
    re.IGNORECASE,
)


class Mode(str, Enum):
    MENTIONED = "mentioned"
    PROACTIVE = "proactive"
    SILENT = "silent"


@dataclass
class Decision:
    mode: Mode
    reason: str
    confidence: float = 0.0

    @property
    def should_respond(self) -> bool:
        return self.mode is not Mode.SILENT


def looks_like_a_question(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < MIN_QUESTION_CHARS:
        return False
    if _NOT_FOR_US.search(t):
        return False
    return t.endswith("?") or bool(_QUESTION_OPENERS.match(t))


def best_match_score(text: str, collection) -> float:
    """How well the project's sources answer this. 0.0 when nothing is indexed."""
    try:
        if collection is None or collection.count() == 0:
            return 0.0
        res = collection.query(query_texts=[text], n_results=3, include=["distances"])
        distances = res.get("distances", [[]])[0]
        if not distances:
            return 0.0
        return max(1.0 - float(d) for d in distances)
    except Exception:
        return 0.0


def decide(message: IncomingMessage, collection) -> Decision:
    """
    Whether to speak, and why. The reason is kept because "the agent said
    nothing" is a thing people ask about, and "it wasn't confident enough" is a
    far better answer than a shrug.
    """
    if message.mentioned_agent:
        return Decision(Mode.MENTIONED, "addressed directly")

    if not (message.text or "").strip():
        return Decision(Mode.SILENT, "empty message")

    if not looks_like_a_question(message.text):
        return Decision(Mode.SILENT, "not a question")

    score = best_match_score(message.text, collection)
    if score < RELEVANCE_FLOOR:
        return Decision(
            Mode.SILENT,
            f"a question, but nothing in this project is related (best match {score:.2f})",
            score,
        )

    # Worth answering. Whether it gets posted is decided after the agent has
    # tried — see should_post().
    return Decision(
        Mode.PROACTIVE,
        f"a project-shaped question worth attempting (best match {score:.2f})",
        score,
    )


def should_post(answer: str, citations: list[dict], mode: Mode) -> tuple[bool, str]:
    """
    The final gate: does this answer earn a place in someone's channel?

    Being asked directly always earns a reply, even "I don't know" — ignoring a
    direct question is worse than admitting ignorance. But speaking unbidden
    requires evidence, and evidence means citations.
    """
    if mode is Mode.MENTIONED:
        return True, "asked directly"
    if not citations:
        return False, "the agent could not cite a source, so it says nothing"
    if len(answer.strip()) < 40:
        return False, "answer too thin to be worth interrupting for"
    return True, f"answered with {len(citations)} source(s)"
