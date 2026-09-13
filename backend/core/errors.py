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


_QUOTA = re.compile(r"tokens per day|TPD|daily limit", re.I)
_MODEL_IN_ERROR = re.compile(r"model `([^`]+)`|model ([\w./-]+)", re.I)


def is_quota_error(exc: BaseException | str) -> bool:
    """A daily cap, as opposed to a per-minute rate limit worth retrying."""
    return bool(_QUOTA.search(str(exc)))


def model_named_in(exc: BaseException | str) -> str | None:
    m = _MODEL_IN_ERROR.search(str(exc))
    return (m.group(1) or m.group(2)) if m else None


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
