"""Fuel refill (abastecimento) model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel, TenantMixin


class FuelRefill(TenantMixin, BaseModel):
    """Registro de abastecimento vinculado ao frete e motorista em viagem."""

    __tablename__ = "tm_fuel_refills"

    freight_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_freights.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_drivers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    truck_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_trucks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
        unique=True,
    )
    litros: Mapped[float] = mapped_column(Float, nullable=False)
    valor_total: Mapped[float] = mapped_column(Float, nullable=False)
    valor_litro: Mapped[float | None] = mapped_column(Float, nullable=True)
    km_atual: Mapped[float | None] = mapped_column(Float, nullable=True)
    posto: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_abastecimento: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    freight: Mapped["Freight"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        lazy="noload"
    )
