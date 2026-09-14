import asyncio
import re
import time
from dataclasses import dataclass, field

from strands import Agent, ModelRetryStrategy
from strands.hooks import AfterInvocationEvent, AfterModelCallEvent, HookProvider, HookRegistry
from strands.types.exceptions import ModelThrottledException

from core.config import settings

# Models that hit their daily cap, with when. Skipped for an hour, then tried
# again — the cap is a rolling window, and a model that was dead at 9am may be
# back by 10. Process-local on purpose: a restart is a fine way to reset it.
_EXHAUSTED: dict[str, float] = {}
_EXHAUSTED_FOR = 3600.0


def limit_kind(exc) -> str:
    """Which limit a provider error names, for the log: "tokens per day (TPD): Limit 200000, Used 199k"."""
    text = str(exc or "")
    m = re.search(r"on ([a-z ]+\([A-Z]+\)): Limit (\d+), Used (\d+), Requested (\d+)", text)
    if m:
        return f"{m.group(1)} used {m.group(3)}/{m.group(2)}, asked {m.group(4)}"
    m = re.search(r"(tokens per day|tokens per minute|requests per (?:day|minute)|Request too large)", text, re.I)
    wait = re.search(r"try again in ([\dhms.]+)", text)
    return " ".join(x for x in ((m.group(1) if m else type(exc).__name__), (f"retry in {wait.group(1)}" if wait else "")) if x)


def mark_exhausted(model_id: str | None, seconds: float = _EXHAUSTED_FOR, why=None) -> None:
    """Bench a model: an hour for a daily cap, about a minute for a per-minute limit."""
    if model_id:
        _EXHAUSTED[model_id] = time.time() + seconds
        span = "an hour" if seconds >= 3600 else f"{int(seconds)}s"
        reason = f" ({limit_kind(why)})" if why is not None else ""
        print(f"[models] {model_id} is at its limit — routing around it for {span}{reason}")


def _usable(model_id: str) -> bool:
    until = _EXHAUSTED.get(model_id)
    return until is None or time.time() > until


async def retry_on_quota(fn, *args, **kwargs):
    """
    Run a background job; if a model's daily quota ended it, route around that
    model and run it once more. Agents are built inside `fn`, so the retry
    picks up the fallback automatically.
    """
    from core.errors import is_quota_error
    try:
        return await fn(*args, **kwargs)
    except Exception as exc:
        if not is_quota_error(exc):
            raise
        # Rest the model that failed. Resting "the first background model" for an
        # hour took healthy models out of chat after one background hiccup.
        bench_for(exc, background=True)
        return await fn(*args, **kwargs)


GROQ_BASE = "https://api.groq.com/openai/v1"

# Output tokens a model will accept per minute, where a provider caps it far
# below the rest. Groq's Qwen models refuse any request whose output budget is
# over 1,000, so asking for the usual 8,000 made them useless as fallbacks.
_OUTPUT_CAPS = {"qwen/qwen3.8-27b": 900, "qwen/qwen3.6-27b": 900}
CHAT_OUTPUT_TOKENS = 2000


# Groq's Qwen models think out loud before answering, and every thinking token
# comes out of the same 900-token output budget: a turn could spend it all
# reasoning and fail before writing a word, and what reasoning did reach the
# answer arrived wrapped in </think>. Chat does not need it; switched off.
_NO_REASONING = {"reasoning_effort": "none", "reasoning_format": "hidden"}


def request_params(model_id: str, background: bool) -> dict:
    """What goes into every request to this model beyond the messages."""
    params = {"max_tokens": max_output_tokens(model_id, background)}
    if model_id.startswith("qwen/"):
        # Groq-only fields: the OpenAI client refuses unknown keyword arguments,
        # so they travel in the request body untouched.
        params["extra_body"] = dict(_NO_REASONING)
    return params


def output_capped(model_id: str | None) -> bool:
    """A model (bare id or provider/model key) whose output budget is too small for long answers or files."""
    if not model_id:
        return False
    return model_id in _OUTPUT_CAPS or model_id.split("/", 1)[-1] in _OUTPUT_CAPS


def max_output_tokens(model_id: str, background: bool) -> int:
    """A chat answer is a few paragraphs; background reports need more room."""
    wanted = settings.MAX_OUTPUT_TOKENS if background else min(settings.MAX_OUTPUT_TOKENS, CHAT_OUTPUT_TOKENS)
    return min(wanted, _OUTPUT_CAPS.get(model_id, wanted))

# Free, hosted, OpenAI-compatible. Each becomes part of the chain when its key
# is present, so an exhausted Groq day falls through to Cerebras, then Gemini,
# then OpenRouter, without anyone editing a flag.
_PROVIDERS = [
    # Anthropic is the one paid provider; when its key is present it goes first
    # and the free tiers only carry the load if it is unavailable.
    ("anthropic", None, "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_BACKGROUND_MODEL"),
    ("groq", GROQ_BASE, "GROQ_API_KEY", "GROQ_MODEL", "GROQ_BACKGROUND_MODEL"),
    ("cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "CEREBRAS_MODEL", "CEREBRAS_BACKGROUND_MODEL"),
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_BACKGROUND_MODEL"),
    ("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_BACKGROUND_MODEL"),
]


def model_chain(background: bool) -> list[tuple[str, str, str, str]]:
    """(key, provider, base_url, model_id) in the order they should be tried."""
    chain = []
    for name, base, key_env, model_env, bg_env in _PROVIDERS:
        api_key = getattr(settings, key_env, "")
        if not api_key:
            continue
        preferred = getattr(settings, bg_env if background else model_env)
        models = [preferred]
        if name == "groq":
            models += [m.strip() for m in settings.GROQ_FALLBACK_MODELS.split(",") if m.strip()]
            if background:
                # Each Groq model has its own per-minute budget. Background work
                # borrowing the chat model's budget is what leaves a person
                # waiting on a question, so the chat model goes last for it.
                models = [m for m in models if m != settings.GROQ_MODEL] + [settings.GROQ_MODEL]
        if background and name == "groq":
            # Background reports are long structured objects; a model that can
            # write 900 tokens fails them every time, and each failure spends
            # the shared per-minute budget chat needs.
            models = [m for m in models if m not in _OUTPUT_CAPS] or models
        for m in models:
            if m not in [c[3] for c in chain if c[1] == name]:
                chain.append((f"{name}/{m}", name, base, m))
    return chain


def pick_model(background: bool) -> tuple[str, str, str, str]:
    """The first (key, provider, base_url, model) in the chain with quota left."""
    chain = model_chain(background)
    if not chain:
        return ("groq/" + settings.GROQ_MODEL, "groq", GROQ_BASE, settings.GROQ_MODEL)
    for entry in chain:
        if _usable(entry[0]):
            return entry
    return chain[0]


def pick_groq_model(background: bool) -> str:
    """Kept for callers that only need the id; the chain may not be Groq at all."""
    return pick_model(background)[0]


def model_available(model_id: str | None) -> bool:
    """True unless the model is resting after hitting a limit."""
    return _usable(model_id)


def seconds_until_available(background: bool) -> float | None:
    """How long until the first model in the chain is back; None when there is no chain."""
    chain = model_chain(background)
    if not chain:
        return None
    now = time.time()
    return max(0.0, min(_EXHAUSTED.get(key, 0.0) - now for key, *_ in chain))


def rest_after(exc) -> float:
    """How long a model rests after this error: a daily cap, a request it can never fit, or what the provider asked."""
    from core.errors import retry_after_seconds
    text = str(exc)
    if _DAILY.search(text):
        return 3600.0
    if "request too large" in text.lower():
        return 600.0
    return (retry_after_seconds(exc) or 60.0) + 1.0


def bench_for(exc, background: bool) -> str | None:
    """Rest the model an error names, for as long as that error calls for."""
    from core.errors import model_named_in
    named = model_named_in(exc)
    key = next((e[0] for e in model_chain(background) + model_chain(not background)
                if named and e[3] == named), None) or pick_model(background)[0]
    mark_exhausted(key, rest_after(exc), why=exc)
    return key


def providers_status() -> list[dict]:
    """What the fallback chain looks like right now — shown on the Trust page."""
    out = []
    for key, provider, _base, model in model_chain(False) + model_chain(True):
        if any(o["key"] == key for o in out):
            continue
        out.append({"key": key, "provider": provider, "model": model, "usable": _usable(key)})
    return out
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
  (ticket status, open PRs) or about a person's work (use who_did_what — a
  question that names a person or bot and asks what they did goes there first).
- A question usually arrives with the passages already retrieved for it, and
  that counts as your first search. Search again only if they genuinely miss
  what the question needs; never a third time with the same intent. If the
  passages and one more search found nothing, the project does not contain it —
  say so and stop.
- Chain tools toward the goal: look up, then act, then report. When asked to "do"
  something, do it — a colleague asked for a spreadsheet produces a spreadsheet.
- Never take a write action (create, send, update, delete) the person did not
  clearly ask for. Read freely; write only on request.

## How to answer
- Write plain sentences, the way a colleague types in chat. Lead with the answer
  in the first sentence, then the evidence that matters.
- Use **bold** only for the one or two key facts a reader is looking for (a name,
  a date, a window). Most answers need no other formatting.
- Use simple "- " bullets only for three or more parallel items. Never tables,
  headings, horizontal rules, emoji or decorative symbols.
- Never write brackets of any kind around sources, citation markers, reference
  numbers or footnotes: no [1], no 【1】, no 【1†source】, no [Confluence: ...],
  no [repo-name], no "(Source: ...)" and no "Sources:" line. The sources are
  shown under your answer automatically.
- When a source matters to the answer, name it in words: "the deployment runbook
  says", "per KAN-12", "Priya said in #all-sensei".
- Speak about the project, not about your retrieval: never "the search returned…"
  or "in the results I was given", and never name your tools (no
  "search_project_docs", "who_did_what") in an answer.
- Copy facts exactly as the source writes them: commands, versions, dates, days,
  frequencies ("weekly", not "nightly"), amounts and units. Never add a currency
  or unit the source does not state, and never swap one date in a source for
  another date near it.
- Steps, commands and procedures come only from the sources. If the passages
  show a heading but not the steps under it, search once for them; if they are
  still missing, say you could not find the steps. Never fill in a plausible
  command.
- Write only the answer. No narration of what you are about to do ("let me
  check…", "I'll fetch…"), and no offers to look something up that you could
  have looked up.
- If the sources do not cover it, say so honestly in one sentence. Do not
  fabricate project details, ticket states, owners or decisions.
- Say how fresh a fact is when it matters: "synced from Confluence", "live from
  Jira just now".
- Keep it short. Use a code block only for commands or code someone will copy.
- A purely general question (no project angle) can be answered directly.
"""


def _build_model(background: bool = False, entry: tuple | None = None):
    """
    The configured model, for any agent in the system.

    Shared so the chat agent and the background agents that write briefs cannot
    drift onto different backends — one LLM_BACKEND flag moves all of them.

    `background=True` selects the cheaper model. Background work is bounded and
    well-specified — survey these sources, compose this object — and there is a
    lot more of it than there is chat.

    `entry` builds one particular model from the chain, which is how a turn
    moves off a model that has hit its limit.
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
    key, provider, base_url, model_id = entry or pick_model(background)
    if provider == "anthropic":
        from strands.models.anthropic import AnthropicModel
        model = AnthropicModel(
            client_args={"api_key": settings.ANTHROPIC_API_KEY, "max_retries": 0,
                         "timeout": 120.0 if background else 60.0},
            model_id=model_id,
            max_tokens=max_output_tokens(model_id, background),
        )
        model.sensei_key = key
        return model
    api_key = {
        "groq": settings.GROQ_API_KEY, "cerebras": settings.CEREBRAS_API_KEY,
        "gemini": settings.GEMINI_API_KEY, "openrouter": settings.OPENROUTER_API_KEY,
    }.get(provider, settings.GROQ_API_KEY)
    model = OpenAIModel(
        model_id=model_id,
        # No silent retries inside the HTTP client: it honours retry-after for up
        # to a minute per attempt, so a throttled question sat on "Searching"
        # for minutes. ModelFailover moves the turn to another model instead,
        # and says so.
        client_args={"api_key": api_key, "base_url": base_url,
                     "max_retries": 0, "timeout": 120.0 if background else 60.0},
        # A structured report of eight gaps is a lot of tokens in one response,
        # and running out mid-object fails the whole run with
        # "unrecoverable state due to max_tokens limit".
        params=request_params(model_id, background),
    )
    # So a quota error can be pinned on the exact provider/model that raised it.
    model.sensei_key = key
    return model


_RETRY = ModelRetryStrategy(max_attempts=3, initial_delay=2, max_delay=8)

_DAILY = re.compile(r"tokens per day|\bTPD\b|daily limit", re.I)


class ModelFailover(HookProvider):
    """
    A per-minute limit on one model is not a limit on the next.

    Groq's free tier gives each model a few thousand tokens a minute, and a turn
    that searches, reads the catalogue and then answers can spend that in two
    calls. When a call is refused, the agent moves onto the next model with room
    and makes the same call again, keeping every passage and tool result it has
    gathered. When every model is resting, it waits for the first one back if
    that is soon, and says so; anything longer is left to the caller to report.
    """

    def __init__(self, *, background: bool = False, max_moves: int = 6, max_wait_s: float = 30.0):
        self.background = background
        self.max_moves = max_moves
        self.max_wait_s = max_wait_s
        self.on_notice = None   # callable(str), set by whoever is streaming the turn
        self._moves = 0

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(AfterModelCallEvent, self._after_model_call)
        registry.add_callback(AfterInvocationEvent, self._after_invocation)

    async def _after_invocation(self, event) -> None:
        self._moves = 0

    def _tell(self, message: str) -> None:
        if self.on_notice is not None:
            try:
                self.on_notice(message)
            except Exception:
                pass

    async def _after_model_call(self, event) -> None:
        from core.errors import is_quota_error, is_rate_limit_error, retry_after_seconds

        exc = event.exception
        if event.retry:
            return
        if exc is None:
            stop = getattr(getattr(event, "stop_response", None), "stop_reason", None)
            if stop == "max_tokens":
                await self._outgrew(event)
            return
        if _rejects_reasoning_params(exc) and self._drop_reasoning_params(event):
            event.retry = True
            return
        if not (isinstance(exc, ModelThrottledException) or is_quota_error(exc) or is_rate_limit_error(exc)):
            return
        if self._moves >= self.max_moves:
            return
        self._moves += 1
        said = retry_after_seconds(exc)

        if settings.LLM_BACKEND in ("bedrock", "ollama"):
            # One configured model and no chain to move along: back off, retry it.
            await asyncio.sleep(min(said or 4 * 2 ** (self._moves - 1), self.max_wait_s))
            event.retry = True
            return

        current = getattr(event.agent.model, "sensei_key", None)
        mark_exhausted(current, rest_after(exc), why=exc)

        entry = next((e for e in model_chain(self.background) if _usable(e[0])), None)
        if entry is None:
            wait = seconds_until_available(self.background)
            if wait is None or wait > self.max_wait_s:
                return
            print(f"[models] every model is resting; waiting {int(wait) + 1}s")
            self._tell("Taking a little longer to check")
            await asyncio.sleep(wait + 0.5)
            entry = next((e for e in model_chain(self.background) if _usable(e[0])), None)
            if entry is None:
                return

        if current is None:
            # Not a model this chain built; all that can be done is wait and retry.
            await asyncio.sleep(min(said or 5.0, self.max_wait_s))
        elif entry[0] != current:
            event.agent.model = _build_model(self.background, entry=entry)
            print(f"[models] {_short(current)} is resting; moved to {_short(entry[0])}")
            self._tell("Taking a little longer to check")
        event.retry = True


    def _drop_reasoning_params(self, event) -> bool:
        """A provider that does not know the reasoning switches gets the request without them."""
        config = getattr(event.agent.model, "config", None)
        params = (config or {}).get("params") if isinstance(config, dict) else None
        extra = (params or {}).get("extra_body") or {}
        if not params or not any(k in extra or k in params for k in _NO_REASONING) or self._moves >= self.max_moves:
            return False
        self._moves += 1
        kept = {k: v for k, v in params.items() if k not in _NO_REASONING and k != "extra_body"}
        rest = {k: v for k, v in extra.items() if k not in _NO_REASONING}
        if rest:
            kept["extra_body"] = rest
        event.agent.model.update_config(params=kept)
        print(f"[models] {_short(getattr(event.agent.model, 'sensei_key', '') or '?')} rejected the reasoning switches; retrying without them")
        return True

    async def _outgrew(self, event) -> None:
        """
        The answer ran past this model's output budget. On a model with a small
        one, the same call goes to a model with room; the half-written response
        is discarded, so the person never sees it.
        """
        if self._moves >= self.max_moves or settings.LLM_BACKEND in ("bedrock", "ollama"):
            return
        current = getattr(event.agent.model, "sensei_key", None)
        if not output_capped(current):
            return
        roomy = [e for e in model_chain(self.background) if not output_capped(e[3])]
        entry = next((e for e in roomy if _usable(e[0])), None)
        if entry is None and roomy:
            now = time.time()
            wait = max(0.0, min(_EXHAUSTED.get(e[0], 0.0) - now for e in roomy))
            if wait > self.max_wait_s:
                return
            self._tell("Taking a little longer to check")
            await asyncio.sleep(wait + 0.5)
            entry = next((e for e in roomy if _usable(e[0])), None)
        if entry is None:
            return
        self._moves += 1
        event.agent.model = _build_model(self.background, entry=entry)
        print(f"[models] {_short(current)} ran out of room for this answer; moved to {_short(entry[0])}")
        self._tell("Taking a little longer to check")
        event.retry = True


def _rejects_reasoning_params(exc) -> bool:
    """A provider (400) or client (unexpected keyword) that does not accept the reasoning switches."""
    text = str(exc)
    refused = "400" in text or "BadRequest" in type(exc).__name__ or isinstance(exc, TypeError)
    return refused and "reasoning" in text.lower()


# A live tool can answer with a megabyte of JSON: every issue with its author's
# avatar URL, node ids, reactions. All of it is re-sent on each model call in
# the turn, and one GitHub listing was enough to push a request past a
# free-tier model's per-minute budget. The model needs the fields, not the noise.
MAX_TOOL_RESULT_CHARS = 4000
_NOISE_KEY = re.compile(r"(^|_)(url|urls|node_id|avatar|gravatar|reactions|_links|sha|etag|"
                        r"performed_via_github_app|sub_issues_summary|timeline|events|site_admin|"
                        r"user_view_type|followers|following|gists|starred|subscriptions|organizations|repos)($|_)",
                        re.I)


def _compact(value, depth: int = 0):
    import json as _json
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if _NOISE_KEY.search(str(k)) and str(k) not in ("html_url",):
                continue
            if v in (None, "", [], {}):
                continue
            if isinstance(v, dict) and depth >= 1 and {"login"} <= set(v):
                out[k] = v.get("login")                     # a whole user object is one name
                continue
            out[k] = _compact(v, depth + 1)
        return out
    if isinstance(value, list):
        return [_compact(v, depth + 1) for v in value]
    return value


def compact_tool_text(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    """A long tool result, with JSON noise removed and the rest cut to size."""
    import json as _json
    if len(text) <= limit:
        return text
    stripped = text.strip()
    if stripped[:1] in "[{":
        try:
            text = _json.dumps(_compact(_json.loads(stripped)), ensure_ascii=False, separators=(",", ":"))
        except ValueError:
            pass
    if len(text) <= limit:
        return text
    return text[:limit].rsplit("\n", 1)[0] + "\n…(cut here: only the first part was kept. Say so if it matters.)"


class ToolResultTrimmer(HookProvider):
    """Keeps a tool's answer to what a model call can carry."""

    def __init__(self, limit: int = MAX_TOOL_RESULT_CHARS):
        self.limit = limit

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        from strands.hooks import AfterToolCallEvent
        registry.add_callback(AfterToolCallEvent, self._after_tool)

    def _after_tool(self, event) -> None:
        result = event.result or {}
        blocks = result.get("content") or []
        changed = False
        new_blocks = []
        for block in blocks:
            text = block.get("text") if isinstance(block, dict) else None
            if isinstance(text, str) and len(text) > self.limit:
                block = {**block, "text": compact_tool_text(text, self.limit)}
                changed = True
            elif isinstance(block, dict) and "json" in block:
                import json as _json
                raw = _json.dumps(block["json"], ensure_ascii=False)
                if len(raw) > self.limit:
                    block = {"text": compact_tool_text(raw, self.limit)}
                    changed = True
            new_blocks.append(block)
        if changed:
            event.result = {**result, "content": new_blocks}


# Built-in tools that only some questions need. Their schemas are re-sent on
# every model call, so a question about the deploy window does not carry the
# spreadsheet writer or live Jira along with it.
_WANTS_FILE = re.compile(
    r"\b(spreadsheet|excel|xlsx|csv|sheet|workbook|tracker|table|word|docx|document|doc|file|"
    r"handover|hand-over|write[- ]?up|report|memo|notes?|download|export|attach(?:ment|ed)?)\b", re.I)
_WANTS_JIRA = re.compile(
    r"(?i:\b(?:jira|tickets?|issues?|bugs?|sprints?|backlog|epics?|stor(?:y|ies)|blockers?|blocked|"
    r"assigned|assignee|priority|status)\b)|\b[A-Z][A-Z0-9]{1,9}-\d+\b")
_WANTS_WRITE = re.compile(
    r"\b(create|open a|file a|raise|add|post|send|comment|reply|update|edit|change|close|reopen|"
    r"assign|merge|approve|label|delete|remove|move|transition|schedule|invite|publish|push|fork|star)\b",
    re.I)


def wants_file(question: str) -> bool:
    return bool(_WANTS_FILE.search(question or ""))


def wants_jira(question: str) -> bool:
    return bool(_WANTS_JIRA.search(question or ""))


def wants_write(question: str) -> bool:
    return bool(_WANTS_WRITE.search(question or ""))


def _short(key: str) -> str:
    return key.split("/")[-1]


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
    search: object = None
    failover: object = None
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
    grant_session=None,
    history: list[dict] | None = None,
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

    # Sized for free-tier per-minute token budgets: every passage is re-sent on
    # each model call in the turn, so two searches of six short passages keep a
    # whole turn inside one model's budget.
    # A passage is the whole chunk (800 characters plus its provenance line).
    # Cut shorter, the end of every chunk was invisible in every search: the
    # runbook's "Rollback to previous. Takes about 90 seconds" sat past the cut,
    # and a chunk already shown is never shown again, so no search could reach it.
    search_tool, captured = make_search_tool(workspace_id, chroma_client, n_results=6,
                                             passage_chars=1000, budget=3,
                                             allowed_sources=allowed_sources)
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
    if not question or wants_jira(question):
        tools.extend(make_jira_tools(visible))

    work_tools, produced = make_work_tools(workspace_id, user_id)
    if not question or wants_file(question):
        tools.extend(work_tools)

    narration = dict(BUILTIN_NARRATION)
    failover = ModelFailover()
    hooks = [failover, ToolResultTrimmer()]
    refusals: list = []
    if grants and grant_session is None:
        # Callers normally pass a warm session from toolgrants.pool; opening
        # here is the fallback for one-off use (tests, scripts).
        grant_session = GrantSession().open(grants)
    if grant_session is not None:
        limit = max_grant_tools if max_grant_tools is not None else settings.MAX_GRANT_TOOLS_PER_TURN
        offered = grant_session.tools
        if question and not wants_write(question):
            # A reading question does not need forty write tools' schemas. Asked
            # to change something, the write tools come back — and the gate
            # still refuses the ones the owner has not allowed.
            from toolgrants.registry import classify
            offered = [t for t in offered if classify(t.tool_name.split("_", 1)[-1],
                                                      getattr(getattr(t, "mcp_tool", None), "annotations", None)) == "read"]
        tools.extend(select_relevant(offered, question, limit))
        narration.update(grant_session.narration)
        gate = grant_session.gate(on_refusal=lambda name, g: refusals.append({"tool": name, "grant": g}))
        hooks.append(gate)

    kwargs = dict(
        model=_build_model(),
        tools=tools,
        system_prompt=SENSEI_SYSTEM_PROMPT,
        # ModelFailover handles limits by moving to another model; the SDK's
        # own retries, which sleep on the same one, stay off.
        retry_strategy=None,
        # Answers reach people through the stream or the channel, not stdout.
        callback_handler=None,
    )
    if hooks:
        kwargs["hooks"] = hooks
    if session_manager is not None:
        kwargs["session_manager"] = session_manager
    elif history:
        kwargs["messages"] = history

    col = Colleague(
        agent=Agent(**kwargs),
        search=search_tool.unmetered,
        failover=failover,
        citations=captured,
        artifacts=produced,
        narration=narration,
        refusals=refusals,
        unavailable=grant_session.failed if grant_session else [],
    )
    # The session belongs to the pool, not to this turn — closing it here would
    # tear down a connection every other turn is about to use.
    col._grants = None
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
