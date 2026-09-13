"""
An answer with citations is not necessarily an answer.

The agent will cite every document it consulted while saying none of them
contain what was asked. Two features depend on telling those apart: the ledger
(which should record it) and the channel router (which must not post it).
"""
from answers.store import is_worth_recording, looks_like_a_refusal
from channels.router import Mode, should_post

CITED = [{"source_label": "PRD.md"}, {"source_label": "README.md"}]

# Taken verbatim from a real run against the demo workspace.
REAL_REFUSAL = (
    "The indexed project documents do not contain any information about which "
    "cloud provider Sensei is deployed to or who owns the cloud-provider account."
)
REAL_ANSWER = (
    "Sensei supports three model backends, switched with LLM_BACKEND: Bedrock "
    "for production, Groq for development, and Ollama offline."
)


def test_detects_a_refusal_that_cited_sources():
    assert looks_like_a_refusal(REAL_REFUSAL)


def test_does_not_flag_a_real_answer():
    assert not looks_like_a_refusal(REAL_ANSWER)


def test_cited_refusal_still_reaches_the_ledger():
    """The bug this was written for: citations masked a non-answer."""
    assert is_worth_recording("Which cloud provider do we deploy to?", REAL_REFUSAL, CITED)


def test_a_real_answer_does_not_reach_the_ledger():
    assert not is_worth_recording("Which model backends are supported?", REAL_ANSWER, CITED)


def test_greetings_never_reach_the_ledger():
    for greeting in ("hi", "thanks", "ok", "hello there"):
        assert not is_worth_recording(greeting, "Hello!", [])


def test_a_cited_refusal_is_not_posted_to_a_channel():
    posted, why = should_post(REAL_REFUSAL, CITED, Mode.PROACTIVE)
    assert not posted
    assert "could not actually answer" in why


def test_a_real_answer_is_posted():
    posted, _ = should_post(REAL_ANSWER, CITED, Mode.PROACTIVE)
    assert posted


def test_a_direct_question_always_gets_a_reply():
    """Ignoring someone is worse than admitting ignorance."""
    posted, _ = should_post(REAL_REFUSAL, [], Mode.MENTIONED)
    assert posted
