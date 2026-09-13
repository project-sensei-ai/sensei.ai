"""Credentials must not be readable from a database dump."""
from core import secrets

TOKEN = "ghp_averyRealLookingToken1234567890"


def test_encrypts_and_round_trips():
    stored = secrets.encrypt(TOKEN)
    assert stored != TOKEN
    assert TOKEN not in stored
    assert secrets.decrypt(stored) == TOKEN


def test_encryption_is_idempotent():
    """Re-saving a source must not double-encrypt its credential."""
    once = secrets.encrypt(TOKEN)
    assert secrets.encrypt(once) == once


def test_plaintext_from_before_encryption_still_reads():
    """Turning encryption on must not break every existing source at once."""
    assert secrets.decrypt("legacy-plaintext-token") == "legacy-plaintext-token"


def test_dict_round_trip():
    original = {"pat": TOKEN, "api_token": "atat-something"}
    stored = secrets.encrypt_dict(original)
    assert all(not v.startswith("ghp_") and not v.startswith("atat") for v in stored.values())
    assert secrets.decrypt_dict(stored) == original


def test_status_reports_how_a_credential_is_held():
    assert secrets.status({"pat": secrets.encrypt(TOKEN)}) == "encrypted"
    assert secrets.status({"pat": TOKEN}) == "plaintext"
    assert secrets.status({}) == "none"


def test_wrong_key_refuses_rather_than_returning_ciphertext():
    """Handing ciphertext back would send it to GitHub as a token."""
    stored = secrets.encrypt(TOKEN)
    from core.config import settings
    original = settings.SECRET_ENCRYPTION_KEY
    try:
        settings.SECRET_ENCRYPTION_KEY = "a-completely-different-key"
        try:
            secrets.decrypt(stored)
            assert False, "should have raised"
        except RuntimeError as exc:
            assert "does not match" in str(exc)
    finally:
        settings.SECRET_ENCRYPTION_KEY = original
