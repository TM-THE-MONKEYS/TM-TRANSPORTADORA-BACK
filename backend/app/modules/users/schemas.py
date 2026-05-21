"""User schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.shared.enums import UserRole


class UserCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8)
    role: UserRole = UserRole.OPERADOR
    is_active: bool = True

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Senha deve ter pelo menos 8 caracteres")
        if not any(c.isupper() for c in v):
            raise ValueError("Senha deve ter pelo menos uma letra maiúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("Senha deve ter pelo menos um número")
        return v


class UserUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    email: EmailStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
