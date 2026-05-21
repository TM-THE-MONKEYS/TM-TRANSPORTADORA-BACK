"""Auth request/response schemas."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

# Permissions each role receives — mirrors frontend lib/rbac/permissions.ts
_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [
        "dashboard:read",
        "fleet:read",
        "fleet:write",
        "drivers:read",
        "drivers:write",
        "freight:read",
        "freight:write",
        "freight:status",
        "finance:read",
        "tenant:admin",
    ],
    "operacional": [
        "dashboard:read",
        "fleet:read",
        "fleet:write",
        "drivers:read",
        "drivers:write",
        "freight:read",
        "freight:write",
        "freight:status",
    ],
    "financeiro": ["dashboard:read", "finance:read", "freight:read"],
    "motorista": ["freight:read", "freight:status"],
}


def role_to_frontend(role: str) -> str:
    """Map backend role 'operador' → frontend 'operacional'."""
    return "operacional" if role == "operador" else role


def permissions_for_role(role: str) -> list[str]:
    return _ROLE_PERMISSIONS.get(role_to_frontend(role), [])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthUserResponse(BaseModel):
    """User shape expected by the Next.js frontend."""

    id: uuid.UUID
    email: str
    name: str
    role: str
    tenant_id: str
    branch_id: str | None = None
    permissions: list[str]


class LoginResponse(BaseModel):
    """Combined tokens + user returned on login — matches frontend AuthProvider contract."""

    tokens: TokenResponse
    user: AuthUserResponse


class RegisterTenantRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=150)
    admin_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8)
    document: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class MessageResponse(BaseModel):
    message: str
