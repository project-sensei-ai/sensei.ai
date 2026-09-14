import os
import sys
from pathlib import Path

# The suite must not depend on a developer's .env — and encryption tests need a
# known key rather than whatever happens to be configured locally.
os.environ.setdefault("SECRET_ENCRYPTION_KEY", "test-key-for-the-suite-only")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


@pytest.fixture(autouse=True)
def _free_tier_chain_by_default(monkeypatch):
    """Tests describe the free-tier chain unless they set a paid key themselves;
    the developer's own backend/.env must not change what they see."""
    from core.config import settings
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
