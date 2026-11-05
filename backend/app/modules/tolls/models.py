"""Toll charge (pedágio) model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel, SoftDeleteMixin, TenantMixin

_ACTIVE_COST = "freight_cost_id IS NOT NULL AND deleted_at IS NULL"


class TollCharge(TenantMixin, SoftDeleteMixin, BaseModel):
    """Registro de pedágio vinculado ao frete e motorista em viagem."""

    __tablename__ = "tm_toll_charges"
    __table_args__ = (
        Index(
            "uq_tm_toll_charges_freight_cost_active",
            "freight_cost_id",
            unique=True,
            sqlite_where=text(_ACTIVE_COST),
            postgresql_where=text(_ACTIVE_COST),
        ),
    )

    freight_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_freights.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_drivers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    driver_nome: Mapped[str | None] = mapped_column(String(150), nullable=True)
    registrado_por_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    freight_cost_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_freight_costs.id", ondelete="SET NULL"),
        nullable=True,
    )
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    praca: Mapped[str | None] = mapped_column(String(150), nullable=True)
    rodovia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_pedagio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    freight: Mapped[Freight] = relationship(  # type: ignore[name-defined]  # noqa: F821
        lazy="noload"
    )
