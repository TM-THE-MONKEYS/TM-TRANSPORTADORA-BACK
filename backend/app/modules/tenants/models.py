"""Tenant model."""
from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel


class Tenant(BaseModel):
    __tablename__ = "tm_tenants"

    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    documento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    plano: Mapped[str] = mapped_column(String(50), nullable=False, default="free")
