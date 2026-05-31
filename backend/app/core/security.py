"""Security utilities: env validation, input sanitization, rate limiting, security headers, request ID."""

import os, re, html, logging, uuid
from typing import List
from fastapi import FastAPI, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

log = logging.getLogger(__name__)

# ── Shared Rate Limiter ───────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# ── Required Environment Variables ────────────────────────────────────────────

CRITICAL_ENV_VARS = {
    "DATABASE_URL": "PostgreSQL connection string",
    "JWT_SECRET": "JWT signing key (min 32 chars)",
}

HIGH_ENV_VARS = {
    "TWILIO_ACCOUNT_SID": "Twilio account SID for WhatsApp",
    "TWILIO_AUTH_TOKEN": "Twilio auth token",
    "OPENROUTER_API_KEY": "OpenRouter AI API key",
}

OPTIONAL_ENV_VARS = {
    "HF_API_KEY": "HuggingFace inference API key",
    "REDIS_URL": "Redis connection URL (OCR cache)",
    "GSTMIND_DB_PATH": "ChromaDB persistent path (default: data/chromadb)",
    "GSTMIND_EMBEDDING_MODEL": "Embedding model name (default: intfloat/multilingual-e5-small)",
    "ANTHROPIC_API_KEY": "Anthropic Claude API key (GSTMind responder)",
    "CORS_ORIGINS": "Comma-separated allowed origins (default: *)",
}


def validate_env() -> List[str]:
    """Check required env vars. Returns list of warning/error messages."""
    messages = []
    for var, desc in CRITICAL_ENV_VARS.items():
        val = os.getenv(var)
        if not val:
            messages.append(f"CRITICAL: {var} is not set — {desc}")
        elif var == "JWT_SECRET" and len(val) < 32 and val != "vyapaarbandhu-secret-key-change-in-production":
            messages.append(f"WARNING: JWT_SECRET is only {len(val)} chars (min 32 recommended)")

    for var, desc in HIGH_ENV_VARS.items():
        if not os.getenv(var):
            messages.append(f"WARNING: {var} is not set — {desc}")

    jwt_secret = os.getenv("JWT_SECRET", "")
    if jwt_secret in ("vyapaarbandhu-secret-key-change-in-production", "vyapaarbandhu-super-secret-2026-change-this"):
        messages.append("CRITICAL: JWT_SECRET is the default value — CHANGE IT before production")

    if os.getenv("DATABASE_URL", "").endswith("vyapaar_bandhu"):
        messages.append("WARNING: DATABASE_URL points to localhost — not suitable for production")

    return messages


# ── Input Sanitization ───────────────────────────────────────────────────────

_SCRIPT_PATTERN = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_SQL_PATTERN = re.compile(r"(\bSELECT\b.*\bFROM\b|\bDROP\b|\bDELETE\b.*\bFROM\b|\bINSERT\b.*\bINTO\b|\bUNION\b.*\bSELECT\b)", re.IGNORECASE)


def sanitize_text(text: str, strip_html: bool = True, max_length: int = 10000) -> str:
    """Strip HTML tags, remove script tags, truncate, and HTML-escape."""
    if not text:
        return text
    text = _SCRIPT_PATTERN.sub("", text)
    if strip_html:
        text = html.escape(text)
    return text[:max_length]


def sanitize_filename(filename: str) -> str:
    """Remove path traversal and dangerous chars from filename."""
    filename = os.path.basename(filename)
    filename = re.sub(r'[^\w\.\-]', '_', filename)
    return filename[:255]


ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}


def validate_file_upload(content_type: str, file_size: int, max_size_mb: int = 10) -> None:
    """Validate file type and size. Raises HTTPException on failure."""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"File type {content_type} not allowed")
    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(status_code=400, detail=f"File too large ({file_size // 1024 // 1024}MB > {max_size_mb}MB)")


# ── Request ID Middleware ─────────────────────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.request_id = request_id
        with logger.contextualize(request_id=request_id):
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── Security Headers Middleware ───────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Cache-Control"] = "no-store"
        return response


# ── CORS ─────────────────────────────────────────────────────────────────────

def get_cors_origins() -> List[str]:
    origins = os.getenv("CORS_ORIGINS", "*")
    if origins == "*":
        return ["*"]
    return [o.strip() for o in origins.split(",")]


# ── App Warnings ──────────────────────────────────────────────────────────────

STARTUP_WARNINGS = [
    "🔑 LIVE API keys on disk in backend/.env — rotate externally before deploying to production",
    "⏰ JWT tokens expire after 30 days — consider reducing this in production",
    "📁 File uploads now validated (type + size) — but no virus scanning",
    "⚠️  Keys committed in git history (commits 6146fa3, 6020f4b) — rotate all credentials",
]


def log_startup_warnings():
    for w in STARTUP_WARNINGS:
        log.warning(w)


# ── Apply all security middleware to app ──────────────────────────────────────

def apply_security_middleware(app: FastAPI):
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    # CORS is applied in main.py from settings
    log_startup_warnings()

    # Validate env on startup
    msgs = validate_env()
    for m in msgs:
        if m.startswith("CRITICAL"):
            log.error(m)
        else:
            log.warning(m)
