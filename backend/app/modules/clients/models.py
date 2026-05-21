"""Client model."""
from __future__ import annotations

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, SoftDeleteMixin


class Client(SoftDeleteMixin, BaseModel):
    __tablename__ = "tm_clients"

    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    cpf_cnpj: Mapped[str] = mapped_column(String(18), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    endereco: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
