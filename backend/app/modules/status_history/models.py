"""Histórico de mudança de status (frete, motorista, caminhão).

Sem SoftDeleteMixin: o rastro precisa sobreviver à exclusão lógica da entidade.
entity_id é polimórfico (sem FK) porque aponta para tabelas diferentes.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, TenantMixin


class StatusHistory(TenantMixin, BaseModel):
    __tablename__ = "tm_status_history"
    __table_args__ = (
        Index(
            "ix_tm_status_history_entity",
            "tenant_id",
            "entity_type",
            "entity_id",
        ),
    )

    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
