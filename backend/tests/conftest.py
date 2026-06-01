import os
import sys

# Ensure backend/ is on sys.path so 'from app...' imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Required env var defaults (setdefault preserves .env / CI overrides) ──────

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-at-least-32-chars-long!!")
os.environ.setdefault("OPENROUTER_API_KEY", "test-dummy-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-dummy-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest00000000000000000000000000000")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-dummy-token")
os.environ.setdefault("TWILIO_FROM", "whatsapp:+14155238886")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:8080")

# ── Overrides (always applied) ────────────────────────────────────────────────

os.environ["TESTING"] = "true"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["DATABASE_URL"] = "sqlite:///test.db"

# Remove stale test DB from previous runs to avoid duplicate-email conflicts
_db_path = os.path.join(os.path.dirname(__file__), "..", "test.db")
if os.path.isfile(_db_path):
    os.remove(_db_path)
