"""
The answer ledger.

When the agent cannot answer something, that is not a dead end — it is the most
useful signal the product produces. Somebody needed to know a thing, and the
project had not written it down. Discarding that is throwing away the one moment
where you know exactly which missing knowledge actually costs people time.

So unanswered questions are recorded. An owner answers one in a sentence, it is
indexed, and the agent answers it for everybody from then on. The project gets
documented by being used.

Detection reuses the signal the channel router settled on: an answer with no
citations is an answer the agent could not ground.
"""
import re
from datetime import datetime, timezone
from uuid import uuid4

from db.chroma import get_workspace_collection

SOURCE_ID = "team_answers"
SOURCE_LABEL = "Team answers"

# Things that are not project questions and should never enter the ledger.
_SMALL_TALK = re.compile(
    r"^\s*(hi|hey|hello|thanks|thank you|ok|okay|cool|nice|got it|yes|no)\b",
    re.IGNORECASE,
)

# Citations record where the agent looked, not that it found an answer. It will
# happily cite six documents while saying none of them say. So the words matter
# too: this catches the agent declining despite having searched.
_DECLINED = re.compile(
    r"(do(es)?n'?t contain|do(es)? not contain|could ?n'?t find|can ?n'?t find|"
    r"cannot find|unable to find|no (information|mention|record|details?)|"
    r"not (documented|specified|stated|mentioned|available|covered)|"
    r"do(es)? not (say|specify|mention|state|appear)|"
    r"is ?n'?t (documented|specified|mentioned)|"
    r"nothing (in|about)|no definitive|not enough information|"
    r"(do(es)?n'?t|do(es)? not) (see|have|show|hold|include)|"
    r"not (in|covered by|part of) (the |our |any )?(project(?:'s)? )?(sources|documentation|docs))",
    re.IGNORECASE,
)


def looks_like_a_refusal(answer: str) -> bool:
    """Whether the agent said it could not answer, regardless of what it cited."""
    return bool(_DECLINED.search(answer or ""))


def _normalise(question: str) -> str:
    """For duplicate detection. Crude on purpose — see record()."""
    return re.sub(r"[^a-z0-9 ]", "", question.lower()).strip()


def is_worth_recording(question: str, answer: str, citations: list) -> bool:
    """
    Whether a question earns a place in the ledger.

    Uncited means ungrounded, which is the whole signal. But a greeting is also
    uncited, and a ledger full of "hi" is a ledger nobody reads.
    """
    q = (question or "").strip()
    if len(q) < 12 or _SMALL_TALK.match(q):
        return False

    declined = looks_like_a_refusal(answer)

    # No citations means nothing was grounded. Citations plus a refusal means it
    # searched, found adjacent material, and still could not answer — which is
    # the more interesting case, because the project nearly documents this.
    if citations and not declined:
        return False

    # An agent answering general programming knowledge is working as intended.
    # Those answers run long and confident; a genuine "I could not find that" is
    # short and hedged.
    if not declined and len(answer or "") > 1200:
        return False
    return True


async def record(db, workspace_id: str, question: str, asked_by: dict, session_id: str) -> None:
    """
    Log a question the agent could not ground.

    Repeats bump a counter rather than adding a row — "asked 4 times" is what
    tells an owner which gap to close first. Matching is on normalised text, so
    it catches "how do I deploy?" twice but not "how do I deploy" versus "what's
    the deploy process". Embedding-based matching would catch both and is the
    obvious next step.
    """
    now = datetime.now(timezone.utc)
    key = _normalise(question)
    existing = await db.unanswered.find_one(
        {"workspace_id": workspace_id, "question_key": key, "status": "open"}
    )
    if existing:
        await db.unanswered.update_one(
            {"_id": existing["_id"]},
            {"$inc": {"times_asked": 1}, "$set": {"last_asked_at": now}},
        )
        return

    await db.unanswered.insert_one({
        "_id": uuid4().hex,
        "workspace_id": workspace_id,
        "question": question.strip(),
        "question_key": key,
        "asked_by_id": asked_by.get("id"),
        "asked_by_name": asked_by.get("name") or asked_by.get("email"),
        "session_id": session_id,
        "times_asked": 1,
        "status": "open",
        "answer": None,
        "answered_by": None,
        "answered_at": None,
        "created_at": now,
        "last_asked_at": now,
    })


async def answer(db, chroma_client, workspace_id: str, entry_id: str,
                 text: str, answered_by: dict) -> dict | None:
    """
    Record a human's answer and index it, so the agent has it from now on.

    Indexed with the question attached, because people ask the question, not the
    answer — embedding only the answer would make it hard to retrieve with the
    words that prompted it.
    """
    entry = await db.unanswered.find_one({"_id": entry_id, "workspace_id": workspace_id})
    if not entry:
        return None

    now = datetime.now(timezone.utc)
    who = answered_by.get("name") or answered_by.get("email") or "a teammate"

    document = (
        f"[{SOURCE_LABEL} › {entry['question'][:80]}]\n"
        f"Question: {entry['question']}\n"
        f"Answer: {text.strip()}\n"
        f"Answered by {who} on {now.date().isoformat()}."
    )
    collection = get_workspace_collection(chroma_client, workspace_id)
    collection.upsert(
        ids=[f"{SOURCE_ID}_{entry_id}"],
        documents=[document],
        metadatas=[{
            "source_id": SOURCE_ID,
            "source_label": SOURCE_LABEL,
            "data_type": "team_answer",
            "title": entry["question"][:80],
            "answered_by": who,
            "chunk": 0,
        }],
    )

    await db.unanswered.update_one(
        {"_id": entry_id},
        {"$set": {"status": "answered", "answer": text.strip(),
                  "answered_by": who, "answered_at": now}},
    )
    return {**entry, "status": "answered", "answer": text.strip(), "answered_by": who}


async def stats(db, workspace_id: str) -> dict:
    """
    How often the agent handles a question without a human having to.

    The number this product lives or dies on — and it should climb as the ledger
    gets worked through.
    """
    open_count = await db.unanswered.count_documents({"workspace_id": workspace_id, "status": "open"})
    answered = await db.unanswered.count_documents({"workspace_id": workspace_id, "status": "answered"})
    dismissed = await db.unanswered.count_documents({"workspace_id": workspace_id, "status": "dismissed"})

    total_asked = 0
    grounded = 0
    async for s in db.chat_sessions.find({"workspace_id": workspace_id}):
        for m in s.get("messages", []):
            if m.get("role") == "assistant":
                total_asked += 1
                if m.get("citations"):
                    grounded += 1

    return {
        "open": open_count,
        "answered_by_humans": answered,
        "dismissed": dismissed,
        "answers_given": total_asked,
        "answers_with_sources": grounded,
        "without_a_human_pct": round(100 * grounded / total_asked) if total_asked else 0,
    }
