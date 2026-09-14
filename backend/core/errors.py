"""
Turning provider failures into sentences.

Everything here surfaced verbatim at some point today. A rate limit arrived as
300 characters of nested JSON naming an organisation id; a missing Bedrock
entitlement as "Operation not allowed"; an exhausted context window as "Agent
has reached an unrecoverable state due to max_tokens limit".

None of that tells the person reading it what happened or what to do, and all of
it will be on screen during a demo if it is not translated.
"""
import re

# Each entry: a matcher, what happened, what to do about it.
_KNOWN = [
    (re.compile(r"tokens per day|TPD", re.I),
     "The model provider's daily limit has been reached.",
     "It resets on a rolling daily window, or switch LLM_BACKEND to another provider."),
    (re.compile(r"rate.?limit|429", re.I),
     "The model provider is rate limiting us.",
     "Wait a moment and try again."),
    (re.compile(r"max_tokens limit|unrecoverable state", re.I),
     "The answer grew past the model's output limit.",
     "Ask for something narrower, or raise MAX_OUTPUT_TOKENS."),
    (re.compile(r"Operation not allowed|AccessDenied.*bedrock", re.I),
     "Bedrock refused the request — this AWS account has not been granted access to the model.",
     "Enable it once from the Bedrock console, then retry."),
    (re.compile(r"NoCredentialsError|Unable to locate credentials", re.I),
     "No AWS credentials are configured.",
     "Set AWS keys in the environment, or attach an instance role."),
    (re.compile(r"invalid.?api.?key|401|Unauthorized|authentication", re.I),
     "The model provider rejected our API key.",
     "Check the key in the environment."),
    (re.compile(r"tool_use_failed|Tool choice is none", re.I),
     "The model tried to use a tool when it was not allowed to.",
     "Usually transient — try again."),
    (re.compile(r"Every model Sensei can use", re.I),
     None,
     None),
    (re.compile(r"SECRET_ENCRYPTION_KEY", re.I),
     None,   # These messages are already written for a person.
     None),
    (re.compile(r"timed out|timeout", re.I),
     "That took longer than the time allowed.",
     "Try again, or narrow the question."),
    (re.compile(r"ServerSelectionTimeout|Connection refused|ConnectionError", re.I),
     "Could not reach a service we depend on.",
     "Check that MongoDB and the model provider are reachable."),
]


# A daily cap, or a request this model's per-minute allowance can never fit —
# either way the fix is another model, not a retry.
_QUOTA = re.compile(r"tokens per day|TPD|daily limit|Request too large", re.I)
_MODEL_IN_ERROR = re.compile(r"model `([^`]+)`|model ([\w./-]+)", re.I)


_RATE = re.compile(r"rate.?limit|\b429\b|tokens per minute|\bTPM\b|ITPM|requests per minute|\bRPM\b|ModelThrottled|throttl", re.I)


def is_rate_limit_error(exc: BaseException | str) -> bool:
    """A per-minute limit: that model is busy, another one may not be."""
    text = f"{type(exc).__name__ if isinstance(exc, BaseException) else ''} {exc}"
    return bool(_RATE.search(text))


def is_quota_error(exc: BaseException | str) -> bool:
    """A daily cap, as opposed to a per-minute rate limit worth retrying."""
    return bool(_QUOTA.search(str(exc)))


def model_named_in(exc: BaseException | str) -> str | None:
    m = _MODEL_IN_ERROR.search(str(exc))
    return (m.group(1) or m.group(2)) if m else None


_RETRY_AFTER = re.compile(r"try again in\s+(?:(\d+)h)?\s*(?:(\d+)m(?!s))?\s*(?:(\d+(?:\.\d+)?)(ms|s))?", re.I)


def retry_after_seconds(exc: BaseException | str) -> float | None:
    """How long the provider said to wait: "Please try again in 1m12.5s" is 72.5."""
    m = _RETRY_AFTER.search(str(exc))
    if not m or not any(m.group(i) for i in (1, 2, 3)):
        return None
    hours, minutes, amount, unit = m.groups()
    seconds = float(amount or 0) / (1000 if (unit or "").lower() == "ms" else 1)
    return int(hours or 0) * 3600 + int(minutes or 0) * 60 + seconds


def humanise(exc: BaseException | str, fallback: str = "Something went wrong.") -> str:
    """
    A sentence a person can act on, instead of a provider's stack trace.

    Unrecognised errors are still truncated and returned — hiding them entirely
    would make a genuinely novel failure impossible to debug from a screenshot.
    """
    raw = str(exc).strip()
    if not raw:
        return fallback

    for pattern, what, action in _KNOWN:
        if pattern.search(raw):
            if what is None:
                return raw[:300]          # already human
            return f"{what} {action}" if action else what

    # Nothing matched. Strip the noisiest framing and keep it short.
    cleaned = re.sub(r"\s+", " ", raw)
    cleaned = re.sub(r"^[\w.]*Error(?: code)?:?\s*", "", cleaned)
    return cleaned[:240] or fallback
