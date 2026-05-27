"""Tenant schemas."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class TenantRead(BaseModel):
    id: uuid.UUID
    nome: str
    documento: str | None = None
    is_active: bool
    plano: str

    model_config = {"from_attributes": True}


class TenantCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    documento: str | None = Field(default=None, max_length=20)
    plano: str = Field(default="free", max_length=50)
