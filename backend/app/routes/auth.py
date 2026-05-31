from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from loguru import logger
from app.core.database import get_db
from app.models.base import CAPartner
from app.core.auth_utils import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token, get_current_ca,
    hash_refresh_token, verify_refresh_token,
)
from app.core.security import limiter, sanitize_text

router = APIRouter(prefix="/auth", tags=["Auth"])

# ── Per-user login throttle ──────────────────────────────────────────────────

_LOGIN_ATTEMPTS: dict[str, dict] = {}
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def _check_login_throttle(email: str):
    record = _LOGIN_ATTEMPTS.get(email.lower())
    if record and record["count"] >= _MAX_FAILED_ATTEMPTS:
        elapsed = __import__("time").time() - record["locked_at"]
        if elapsed < _LOCKOUT_MINUTES * 60:
            remaining = int(_LOCKOUT_MINUTES * 60 - elapsed)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many login attempts. Try again in {remaining} seconds.",
            )
        del _LOGIN_ATTEMPTS[email.lower()]


def _record_failed_login(email: str):
    key = email.lower()
    now = __import__("time").time()
    if key not in _LOGIN_ATTEMPTS:
        _LOGIN_ATTEMPTS[key] = {"count": 0, "locked_at": now}
    _LOGIN_ATTEMPTS[key]["count"] += 1
    _LOGIN_ATTEMPTS[key]["locked_at"] = now


def _reset_login_throttle(email: str):
    _LOGIN_ATTEMPTS.pop(email.lower(), None)


# ── Schemas ───────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name:             str
    email:            str
    password:         str
    phone:            str | None = None
    ca_number:        str | None = None
    white_label_name: str | None = None


class LoginRequest(BaseModel):
    email:    str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    ca_id:         int
    name:          str
    email:         str
    plan:          str
    white_label_name: str | None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=AuthResponse)
@limiter.limit("5/minute")
def signup(request: Request, req: SignupRequest, db: Session = Depends(get_db)):
    """Register a new CA account."""

    req.name = sanitize_text(req.name.strip(), max_length=100)
    req.email = req.email.lower().strip()

    existing = db.query(CAPartner).filter(CAPartner.email == req.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered. Please login."
        )

    if len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters."
        )

    ca = CAPartner(
        name             = req.name,
        email            = req.email,
        password_hash    = hash_password(req.password),
        phone            = req.phone,
        ca_number        = req.ca_number,
        white_label_name = req.white_label_name or req.name,
        plan             = "starter",
        is_active        = True
    )
    db.add(ca)
    db.commit()
    db.refresh(ca)

    access_token = create_access_token(ca.id, ca.email)
    refresh_token = create_refresh_token(ca.id, ca.email)
    ca.refresh_token_hash = hash_refresh_token(refresh_token)
    db.commit()

    logger.info(f"New CA registered: {ca.email} | ID: {ca.id}")

    return AuthResponse(
        access_token     = access_token,
        refresh_token    = refresh_token,
        ca_id            = ca.id,
        name             = ca.name,
        email            = ca.email,
        plan             = ca.plan,
        white_label_name = ca.white_label_name
    )


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    """Login for existing CA."""

    _check_login_throttle(req.email)

    ca = db.query(CAPartner).filter(CAPartner.email == req.email.lower().strip()).first()

    if not ca or not verify_password(req.password, ca.password_hash):
        _record_failed_login(req.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not ca.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Contact support."
        )

    _reset_login_throttle(req.email)
    access_token = create_access_token(ca.id, ca.email)
    refresh_token = create_refresh_token(ca.id, ca.email)
    ca.refresh_token_hash = hash_refresh_token(refresh_token)
    db.commit()

    logger.info(f"CA logged in: {ca.email} | ID: {ca.id}")

    return AuthResponse(
        access_token     = access_token,
        refresh_token    = refresh_token,
        ca_id            = ca.id,
        name             = ca.name,
        email            = ca.email,
        plan             = ca.plan,
        white_label_name = ca.white_label_name
    )


@router.post("/refresh")
@limiter.limit("10/minute")
def refresh_token(request: Request, req: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a refresh token for a new access + refresh token (rotation)."""
    payload = decode_token(req.refresh_token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type — use a refresh token"
        )

    ca = db.query(CAPartner).filter(CAPartner.id == int(payload["sub"])).first()
    if not ca or not ca.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CA account not found or inactive"
        )

    if not ca.refresh_token_hash or not verify_refresh_token(req.refresh_token, ca.refresh_token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked — please log in again"
        )

    # Rotate: issue new tokens, invalidate old refresh token
    new_access_token = create_access_token(ca.id, ca.email)
    new_refresh_token = create_refresh_token(ca.id, ca.email)
    ca.refresh_token_hash = hash_refresh_token(new_refresh_token)
    db.commit()

    logger.info(f"Token refreshed for: {ca.email} | ID: {ca.id}")

    return {"access_token": new_access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}


@router.get("/me")
def get_me(ca: CAPartner = Depends(get_current_ca)):
    """Get current CA profile."""
    return {
        "ca_id":            ca.id,
        "name":             ca.name,
        "email":            ca.email,
        "phone":            ca.phone,
        "ca_number":        ca.ca_number,
        "plan":             ca.plan,
        "white_label_name": ca.white_label_name,
        "created_at":       str(ca.created_at)
    }


@router.put("/profile")
def update_profile(
    data: dict,
    ca: CAPartner = Depends(get_current_ca),
    db: Session = Depends(get_db)
):
    """Update CA profile."""
    allowed = ["name", "phone", "ca_number", "white_label_name"]
    for key in allowed:
        if key in data:
            setattr(ca, key, data[key])
    db.commit()
    return {"success": True, "message": "Profile updated."}
