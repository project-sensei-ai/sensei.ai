"""Chat routes — session management + the colleague answering, streamed."""
import asyncio
import json
import re
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.agent import build_colleague, make_session_manager
from answers import store as answer_store
from artifacts.routes import serialize_artifact
from auth.deps import get_current_user
from core.formatting import plain_answer, without_reasoning
from agent.tools import relevant_citations
from core.errors import humanise, is_quota_error, is_rate_limit_error, model_named_in
from agent.agent import mark_exhausted, model_available, pick_model, rest_after
from db.chroma import get_chroma
from db.database import get_db
from db.membership import require_workspace, visible_sources
from db.models import serialize_chat_session
from toolgrants import registry as grants
from toolgrants import pool

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _require_session(session_id: str, user, db):
    session = await db.chat_sessions.find_one({"_id": session_id, "owner_id": user["id"], "archived": False})
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


async def _equip(db, chroma, session: dict, user: dict, session_id: str, question: str = ""):
    """
    Everything one turn needs, resolved before the model runs: which sources
    this person may be answered from, which tools the owner granted, and which
    Atlassian credential (if any) makes Jira live.
    """
    ws = session["workspace_id"]
    allowed = await visible_sources(db, ws, user["id"])
    sources = [s async for s in db.sources.find({"workspace_id": ws})]
    grant_docs = await grants.load_grants(db, ws)
    grant_session = await pool.get_session(ws, grant_docs)
    col = await asyncio.to_thread(
        build_colleague,
        ws, chroma,
        sources=sources, grants=grant_docs, user_id=user["id"],
        session_manager=make_session_manager(session_id), allowed_sources=allowed,
        question=question, grant_session=grant_session,
    )
    return col


async def _persist_turn(db, session: dict, session_id: str, question: str, answer: str,
                        citations: list, artifacts: list, user: dict, tools_used: list[str],
                        steps: list[dict] | None = None, duration_ms: int | None = None) -> list[dict]:
    """Store the exchange, the files it produced, and — if it went unanswered — the question.

    The answer is stored as plain text, and with the steps the turn showed while
    it worked, so a finished message can still say how it got there. Callers
    pass the answer already cleaned by `plain_answer`, so what is stored is
    exactly what the person was sent.
    """
    now = datetime.now(timezone.utc).isoformat()
    saved = []
    for art in artifacts:
        art = {**art, "session_id": session_id}
        await db.artifacts.insert_one(art)
        saved.append(serialize_artifact(art))

    is_first = len(session.get("messages", [])) == 0
    title_update = {"title": question[:60] + ("…" if len(question) > 60 else "")} if is_first else {}
    await db.chat_sessions.update_one(
        {"_id": session_id},
        {
            "$set": {"updated_at": datetime.now(timezone.utc), **title_update},
            "$push": {"messages": {"$each": [
                {"role": "user", "content": question, "created_at": now},
                {"role": "assistant", "content": answer, "citations": citations,
                 "artifacts": saved, "tools_used": tools_used,
                 "steps": steps or [], "duration_ms": duration_ms, "created_at": now},
            ]}},
        },
    )
    for name in tools_used:
        await grants.touch(db, session["workspace_id"], name)

    # An uncited answer is an ungrounded one — unless the turn was *work*
    # (a file, a live lookup, a tool action), where citations are beside the point.
    did_work = bool(artifacts) or any(
        n in ("jira_search", "jira_issue") or "_" in n and not n.startswith(("search_", "list_", "who_"))
        for n in tools_used
    )
    if not did_work and answer_store.is_worth_recording(question, answer, citations):
        await answer_store.record(db, session["workspace_id"], question, user, session_id)
    return saved


async def _persist_failure(db, session: dict, session_id: str, question: str, message: str,
                           steps: list[dict], duration_ms: int) -> None:
    """
    A turn that failed still happened. Without this the question, the steps
    the person watched and the failure all vanished on reload.
    """
    now = datetime.now(timezone.utc).isoformat()
    is_first = len(session.get("messages", [])) == 0
    title_update = {"title": question[:60] + ("…" if len(question) > 60 else "")} if is_first else {}
    await db.chat_sessions.update_one(
        {"_id": session_id},
        {"$set": {"updated_at": datetime.now(timezone.utc), **title_update},
         "$push": {"messages": {"$each": [
             {"role": "user", "content": question, "created_at": now},
             {"role": "assistant", "content": message, "error": True, "citations": [],
              "artifacts": [], "tools_used": [], "steps": steps, "duration_ms": duration_ms,
              "created_at": now},
         ]}}},
    )


# ── Session endpoints ──────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(user=Depends(get_current_user), db=Depends(get_db)):
    ws, _role = await require_workspace(user, db)
    cursor = db.chat_sessions.find(
        {"workspace_id": ws["_id"], "owner_id": user["id"], "archived": False}
    ).sort("updated_at", -1).limit(50)
    sessions = await cursor.to_list(50)
    return {"sessions": [serialize_chat_session(s) for s in sessions]}


@router.post("/sessions", status_code=201)
async def create_session(user=Depends(get_current_user), db=Depends(get_db)):
    ws, _role = await require_workspace(user, db)
    now = datetime.now(timezone.utc)
    session_id = str(uuid4()).replace("-", "")
    doc = {
        "_id": session_id,
        "workspace_id": ws["_id"],
        "owner_id": user["id"],
        "title": "New chat",
        "messages": [],
        "created_at": now,
        "updated_at": now,
        "archived": False,
    }
    await db.chat_sessions.insert_one(doc)
    return {"session": serialize_chat_session(doc)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    session = await _require_session(session_id, user, db)
    return {"session": serialize_chat_session(session, include_messages=True)}


@router.delete("/sessions/{session_id}", status_code=204)
async def archive_session(session_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    result = await db.chat_sessions.update_one(
        {"_id": session_id, "owner_id": user["id"]},
        {"$set": {"archived": True, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    body: ChatRequest,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """One-shot answer. The streaming route below is what the UI uses."""
    session = await _require_session(session_id, user, db)
    started = time.monotonic()
    col = await _equip(db, get_chroma(request), session, user, session_id, body.question)
    tools_used: list[str] = []
    try:
        passages = await asyncio.to_thread(col.search, query=body.question)
        # Strands Agent.__call__ is synchronous — run it in a thread pool
        response = await asyncio.to_thread(col.agent, _primed(body.question, passages))
        answer = plain_answer(str(response))
        for m in getattr(col.agent, "messages", []) or []:
            for block in m.get("content", []) if isinstance(m, dict) else []:
                if isinstance(block, dict) and "toolUse" in block:
                    tools_used.append(block["toolUse"].get("name", ""))
    finally:
        col.close()

    citations = relevant_citations(col.citations, answer)
    artifacts = await _persist_turn(db, session, session_id, body.question, answer,
                                    citations, col.artifacts, user, tools_used,
                                    duration_ms=int((time.monotonic() - started) * 1000))
    return {"answer": answer, "citations": citations, "artifacts": artifacts}


# ── Streaming ─────────────────────────────────────────────────────────────────
#
# The non-streaming route above answers in one lump, which means a spinner for
# up to forty seconds while the agent searches, reads and reasons. All of that
# work is interesting — it is the evidence that there is an agent here at all —
# and hiding it behind a spinner throws it away.

# How long one question may take before the person is told, and how long a
# silence lasts before they hear it is still being worked on.
TURN_DEADLINE_S = 150
EQUIP_DEADLINE_S = 45
QUIET_AFTER_S = 20
MAX_MODEL_SWITCHES = 3

# A person watching the answer form sees what the agent is doing, in words. A
# model resting at its limit, a slow provider, a switch to another model: all of
# that is plumbing, and it reaches them as one calm line, once.
CALM_STEP = "Taking a little longer to check"


def _primed(question: str, passages: str) -> str:
    """
    The question, with what the sources already say about it.

    Retrieval costs no model tokens, and a model that has to ask for the
    passages spends two or three calls re-reading the whole conversation. On a
    provider that allows 8,000 tokens a minute, that difference is whether a
    question gets answered at all.
    """
    return (
        f"{question}\n\n"
        "<passages_already_retrieved>\n"
        f"{passages}\n"
        "</passages_already_retrieved>\n\n"
        "These passages were retrieved from the project's sources for this question. Answer "
        "from them when they are enough, in plain sentences. Do not copy their bracketed labels "
        "or add citation markers: the sources are shown with your answer, so name one in words "
        "only when it matters. Do not describe the retrieval itself. Use a tool only when they miss something the question needs, or when it asks "
        "for live data, a person's activity, a file, or an action."
    )


async def _pump(stream, queue: asyncio.Queue) -> None:
    """
    Drain the agent's stream inside one task and hand it over through a queue.

    Pulling each chunk from a fresh task broke OpenTelemetry's bookkeeping: a
    span opened in one task was closed from another, and every turn logged a
    traceback. One task owns the stream from first chunk to last.
    """
    try:
        async for chunk in stream:
            await queue.put(("chunk", chunk))
    except Exception as exc:
        await queue.put(("error", exc))
    else:
        await queue.put(("end", None))


class AnswerGate:
    """
    Decides which of the model's text is the answer, while it streams.

    Not all of it is. Text a model writes before calling a tool is narration
    ("I need to fetch the open tickets first"); text before </think> is its
    reasoning; a response a failover discards was never the answer. All of it
    once reached the reader and the stored message: KAN-1's answer carried a
    raw </think> and a second, contradictory answer after it.

    So each model response's text is held until it is plainly the answer — the
    stream ended, or enough of it has arrived that it is answering rather than
    announcing. If a tool call or a retry follows text already shown, the shown
    text is withdrawn with a reset and the answer starts again.
    """

    HOLD_CHARS = 400

    def __init__(self):
        self.cycle = ""       # raw text of the model response in progress
        self.sent = ""        # what the reader has been shown of it
        self.releasing = False

    def _sync(self, clean: str) -> list[dict]:
        events = []
        if not clean.startswith(self.sent):
            events.append({"type": "reset"})
            self.sent = ""
        extra = clean[len(self.sent):]
        if extra:
            events.append({"type": "text", "delta": extra})
            self.sent = clean
        return events

    def feed(self, delta: str) -> list[dict]:
        self.cycle += delta
        clean = without_reasoning(self.cycle).lstrip()
        if not self.releasing:
            if len(clean) < self.HOLD_CHARS or re.search(r"<think>(?!.*</think>)", self.cycle, re.S | re.I):
                return []
            self.releasing = True
        return self._sync(clean)

    def discard(self) -> list[dict]:
        """A tool call is starting, or the response is being retried: what came before was not the answer."""
        events = [{"type": "reset"}] if self.sent else []
        self.cycle, self.sent, self.releasing = "", "", False
        return events

    def finish(self) -> list[dict]:
        return self._sync(without_reasoning(self.cycle).lstrip())

    @property
    def shown(self) -> bool:
        return bool(self.sent)

    @property
    def answer(self) -> str:
        return without_reasoning(self.cycle)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@router.post("/sessions/{session_id}/stream")
async def stream_message(
    session_id: str,
    body: ChatRequest,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Answer over server-sent events: tool calls as they happen, then the answer
    token by token, then citations and any files produced.
    """
    session = await _require_session(session_id, user, db)
    chroma = get_chroma(request)

    async def events():
        gate = AnswerGate()
        announced: set[str] = set()
        tools_used: list[str] = []
        steps: list[dict] = []
        started = time.monotonic()
        state = {"calm": False, "writing": False}
        col = None

        def step(label: str, event: dict | None = None) -> str:
            if not steps or steps[-1]["label"] != label:
                steps.append({"label": label, "ms": int((time.monotonic() - started) * 1000)})
            return _sse(event or {"type": "step", "label": label})

        def calm() -> str | None:
            if state["calm"]:
                return None
            state["calm"] = True
            return step(CALM_STEP)

        try:
            yield step("Reading your question")
            # Resolved before the stream opens; an auth question should not be
            # answered halfway through a response.
            try:
                col = await asyncio.wait_for(_equip(db, chroma, session, user, session_id, body.question),
                                             timeout=EQUIP_DEADLINE_S)
            except asyncio.TimeoutError:
                raise TimeoutError("timed out connecting to this project's tools")
            for u in col.unavailable:
                yield step(f"{u['grant']} is not answering right now, so its tools are skipped this turn")

            # A per-minute limit on one model is not a limit on the next: switch
            # and carry on, as long as nothing has been said yet. And no question
            # waits in silence: a quiet spell gets a calm step, a stuck one a deadline.
            label = col.narration.get("search_project_docs", "Searching the project's documents")
            yield step(label, {"type": "tool", "name": "search_project_docs", "label": label})
            tools_used.append("search_project_docs")
            # The model's answer budget starts once the tools are connected, so a
            # slow tool connection is not blamed on the model provider.
            model_started = time.monotonic()
            for attempt in range(MAX_MODEL_SWITCHES + 1):
                # Each colleague carries its own citation list, so a switch to
                # another model searches again rather than losing the sources.
                passages = await asyncio.to_thread(col.search, query=body.question)
                queue: asyncio.Queue = asyncio.Queue()
                gate.discard()
                if col.failover is not None:
                    # A model hitting its limit mid-turn is handled inside the
                    # agent; the person hears about it through the same queue.
                    col.failover.on_notice = lambda message, q=queue: q.put_nowait(("notice", message))
                pump = asyncio.create_task(
                    _pump(col.agent.stream_async(_primed(body.question, passages)), queue))
                try:
                    while True:
                        remaining = TURN_DEADLINE_S - (time.monotonic() - model_started)
                        if remaining <= 0:
                            raise TimeoutError("timed out waiting for the model provider")
                        try:
                            kind, chunk = await asyncio.wait_for(queue.get(), timeout=min(QUIET_AFTER_S, remaining))
                        except asyncio.TimeoutError:
                            if remaining > QUIET_AFTER_S and (said := calm()):
                                yield said
                            continue
                        if kind == "end":
                            break
                        if kind == "error":
                            raise chunk
                        if kind == "notice":
                            # The failover's own words name models; the person
                            # gets the calm step instead. A notice means the
                            # response in progress is being redone elsewhere.
                            for ev in gate.discard():
                                yield _sse(ev)
                            if said := calm():
                                yield said
                            continue

                        # A tool starting. Announced once per invocation, not once
                        # per streamed fragment of its arguments.
                        tool = chunk.get("current_tool_use")
                        if tool and tool.get("toolUseId") not in announced:
                            announced.add(tool["toolUseId"])
                            # Whatever the model wrote before deciding to use a
                            # tool was narration, not the answer.
                            for ev in gate.discard():
                                yield _sse(ev)
                            name = tool.get("name", "")
                            tools_used.append(name)
                            label = col.narration.get(name, f"Using {name.replace('_', ' ')}")
                            yield step(label, {"type": "tool", "name": name, "label": label})

                        text = chunk.get("data")
                        if text:
                            for ev in gate.feed(text):
                                if ev["type"] == "text" and not state["writing"]:
                                    state["writing"] = True
                                    yield step("Writing the answer")
                                yield _sse(ev)
                    for ev in gate.finish():
                        if ev["type"] == "text" and not state["writing"]:
                            state["writing"] = True
                            yield step("Writing the answer")
                        yield _sse(ev)
                    break
                except TimeoutError:
                    raise
                except Exception as exc:
                    daily = is_quota_error(exc)
                    busy = daily or is_rate_limit_error(exc)
                    if not busy:
                        raise
                    # Reaching here means the agent's own failover ran out of
                    # models with room. Start over on another only if nothing
                    # has been said yet and one is actually available.
                    key = getattr(col.agent.model, "sensei_key", None) or model_named_in(exc)
                    if model_available(key):
                        mark_exhausted(key, rest_after(exc), why=exc)
                    next_key = pick_model(background=False)[0]
                    if (gate.shown or attempt == MAX_MODEL_SWITCHES or next_key == key
                            or not model_available(next_key)):
                        raise RuntimeError(
                            "Every model Sensei can use is busy right now. Try again in a minute."
                        ) from exc
                    col.close()
                    print(f"[chat] switching this turn from {key} to {next_key}")
                    if said := calm():
                        yield said
                    col = await asyncio.wait_for(_equip(db, chroma, session, user, session_id, body.question),
                                                 timeout=EQUIP_DEADLINE_S)
                finally:
                    # A person who closes the tab should not leave a model call running.
                    if not pump.done():
                        pump.cancel()

            answer = plain_answer(gate.answer)
            duration_ms = int((time.monotonic() - started) * 1000)
            col.close()
            citations = relevant_citations(col.citations, answer)
            artifacts = await _persist_turn(db, session, session_id, body.question, answer,
                                            citations, col.artifacts, user, tools_used,
                                            steps=steps, duration_ms=duration_ms)
            yield _sse({"type": "done", "answer": answer, "citations": citations,
                        "artifacts": artifacts, "refusals": col.refusals,
                        "steps": steps, "duration_ms": duration_ms})

        except Exception as exc:
            # The stream has already started, so an HTTP error code is no longer
            # available — the failure has to travel as an event.
            message = humanise(exc)
            print(f"[chat] turn failed: {type(exc).__name__}: {str(exc)[:300]}")
            try:
                await _persist_failure(db, session, session_id, body.question, message, steps,
                                       int((time.monotonic() - started) * 1000))
            except Exception as store_exc:
                print(f"[chat] could not store the failed turn: {store_exc}")
            yield _sse({"type": "error", "message": message})
        finally:
            if col is not None:
                col.close()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # stop proxies holding the stream back
        },
    )
