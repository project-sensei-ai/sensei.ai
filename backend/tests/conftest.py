import os
import sys
from pathlib import Path

# The suite must not depend on a developer's .env — and encryption tests need a
# known key rather than whatever happens to be configured locally.
os.environ.setdefault("SECRET_ENCRYPTION_KEY", "test-key-for-the-suite-only")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
