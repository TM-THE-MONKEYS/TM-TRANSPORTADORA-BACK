"""JWT token creation and validation."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt

from app.core.config.settings import get_settings
from app.shared.enums import UserRole

settings = get_settings()


def create_access_token(
    user_id: UUID,
    role: UserRole,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, object] = {
        "sub": str(user_id),
        "role": role.value,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token() -> tuple[str, str]:
    """Return (raw_token, hashed_token). Store only the hash."""
    raw = secrets.token_urlsafe(64)
    hashed = _hash_token(raw)
    return raw, hashed


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_refresh_token(raw_token: str) -> str:
    return _hash_token(raw_token)


def decode_access_token(token: str) -> dict[str, object]:
    """Decode and validate JWT. Raises JWTError on failure."""
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        options={"verify_exp": True},
    )
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


def create_password_reset_token(user_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.password_reset_token_expire_hours
    )
    payload: dict[str, object] = {
        "sub": str(user_id),
        "exp": expire,
        "type": "password_reset",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_password_reset_token(token: str) -> str:
    """Return user_id string. Raises JWTError on failure."""
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        options={"verify_exp": True},
    )
    if payload.get("type") != "password_reset":
        raise JWTError("Invalid token type")
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise JWTError("Invalid token subject")
    return sub
