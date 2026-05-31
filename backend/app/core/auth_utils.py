import os, hashlib, uuid
import bcrypt
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.base import CAPartner

SECRET_KEY = os.getenv("JWT_SECRET", "vyapaarbandhu-secret-key-change-in-production")
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer()


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── Refresh Token Rotation ────────────────────────────────────────────────────

def hash_refresh_token(token: str) -> str:
    """SHA-256 + bcrypt hash of a refresh token for secure storage."""
    return bcrypt.hashpw(hashlib.sha256(token.encode()).hexdigest().encode(), bcrypt.gensalt()).decode()

def verify_refresh_token(token: str, stored_hash: str) -> bool:
    """Verify a refresh token against its stored hash."""
    return bcrypt.checkpw(hashlib.sha256(token.encode()).hexdigest().encode(), stored_hash.encode())


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(ca_id: int, email: str) -> str:
    payload = {
        "sub":   str(ca_id),
        "email": email,
        "type":  "access",
        "exp":   datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(ca_id: int, email: str) -> str:
    payload = {
        "sub":   str(ca_id),
        "email": email,
        "type":  "refresh",
        "jti":   uuid.uuid4().hex,
        "exp":   datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── Dependency ────────────────────────────────────────────────────────────────

def get_current_ca(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> CAPartner:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type — use an access token"
        )

    ca = db.query(CAPartner).filter(CAPartner.id == int(payload["sub"])).first()

    if not ca or not ca.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CA account not found or inactive"
        )

    return ca