"""
Encryption for stored source credentials.

A GitHub PAT or a Confluence API token sits in the database until someone
deletes the source. Until now they sat there in cleartext, which is hard to
defend in a product whose entire argument is that it handles access carefully.

Fernet (AES-128-CBC with an HMAC) over a key from SECRET_ENCRYPTION_KEY. Not a
KMS — the key still lives in the environment — but it means a database dump is
no longer a pile of working credentials, which is the realistic threat.

Reads tolerate plaintext so existing rows keep working; they are re-encrypted
the next time the source is written. Writes never produce plaintext.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from core.config import settings

_PREFIX = "enc:v1:"


def _fernet() -> Fernet | None:
    """
    The cipher, or None when no key is configured.

    A key of the wrong shape is derived rather than rejected, so operators can
    set any sufficiently long string without knowing Fernet wants 32 url-safe
    base64 bytes.
    """
    raw = (settings.SECRET_ENCRYPTION_KEY or "").strip()
    if not raw:
        return None
    try:
        return Fernet(raw.encode())
    except Exception:
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
        return Fernet(derived)


def is_configured() -> bool:
    return _fernet() is not None


def encrypt(value: str) -> str:
    """Encrypt one value. Returns it unchanged if no key is configured."""
    if not value or value.startswith(_PREFIX):
        return value
    f = _fernet()
    if f is None:
        return value
    return _PREFIX + f.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """
    Decrypt one value.

    Anything without the marker is assumed to predate encryption and is handed
    back as-is — otherwise turning encryption on would break every existing
    source at once.
    """
    if not isinstance(value, str) or not value.startswith(_PREFIX):
        return value
    f = _fernet()
    if f is None:
        # Encrypted data and no key: refuse loudly rather than hand back
        # ciphertext that some caller will try to authenticate with.
        raise RuntimeError(
            "This source's credentials are encrypted but SECRET_ENCRYPTION_KEY is "
            "not set. Restore the key, or delete and reconnect the source."
        )
    try:
        return f.decrypt(value[len(_PREFIX):].encode()).decode()
    except InvalidToken:
        raise RuntimeError(
            "This source's credentials could not be decrypted — "
            "SECRET_ENCRYPTION_KEY does not match the one they were stored with."
        )


def encrypt_dict(secrets: dict | None) -> dict:
    return {k: encrypt(v) if isinstance(v, str) else v for k, v in (secrets or {}).items()}


def decrypt_dict(secrets: dict | None) -> dict:
    return {k: decrypt(v) if isinstance(v, str) else v for k, v in (secrets or {}).items()}


def status(secrets: dict | None) -> str:
    """How a stored credential is held — surfaced on the Trust page."""
    values = [v for v in (secrets or {}).values() if isinstance(v, str) and v]
    if not values:
        return "none"
    if all(v.startswith(_PREFIX) for v in values):
        return "encrypted"
    return "plaintext"
