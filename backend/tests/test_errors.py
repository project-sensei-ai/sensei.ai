"""
Provider failures reach a person, so they have to read like sentences.

Every string below was seen verbatim during development. Each one would have
appeared on screen during a demo.
"""
from core.errors import humanise


def test_a_daily_token_cap_says_what_to_do():
    msg = humanise(
        "Error code: 429 - {'error': {'message': 'Rate limit reached for model "
        "`openai/gpt-oss-120b` in organization `org_01knm` service tier `on_demand` "
        "on tokens per day (TPD): Limit 200000, Used 196538'}}"
    )
    # Says it will come back, without "limit" wording a reader cannot act on.
    assert "later" in msg and "limit" not in msg.lower()
    assert "org_01knm" not in msg          # no internal identifiers
    assert len(msg) < 200


def test_bedrock_without_model_access():
    msg = humanise("An error occurred (ValidationException) when calling the "
                   "ConverseStream operation: Operation not allowed")
    assert "Bedrock" in msg and "console" in msg


def test_output_limit():
    """A member cannot raise a server setting, and "limit" wording is plumbing."""
    msg = humanise("Agent has reached an unrecoverable state due to max_tokens limit.")
    assert "MAX_OUTPUT_TOKENS" not in msg and "limit" not in msg.lower()
    assert "shorter" in msg


def test_messages_already_written_for_a_person_are_left_alone():
    original = ("This source's credentials are encrypted but SECRET_ENCRYPTION_KEY "
                "is not set. Restore the key, or delete and reconnect the source.")
    assert humanise(original) == original


def test_an_unrecognised_failure_is_still_shown():
    """Hiding a novel error makes it undebuggable from a screenshot."""
    assert "brand new failure" in humanise("Some brand new failure nobody has seen")


def test_empty_falls_back():
    assert humanise("") == "Something went wrong."
