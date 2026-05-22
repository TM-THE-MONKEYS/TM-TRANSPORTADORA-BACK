"""Freight models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel, SoftDeleteMixin
from app.shared.enums import FreightStatus


class Freight(SoftDeleteMixin, BaseModel):
    __tablename__ = "tm_freights"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tm_clients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tm_drivers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    truck_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tm_trucks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    origem: Mapped[dict] = mapped_column(JSON, nullable=False)
    destino: Mapped[dict] = mapped_column(JSON, nullable=False)
    valor_frete: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[FreightStatus] = mapped_column(
        Enum(FreightStatus, name="freightstatus", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=FreightStatus.ORCAMENTO,
        index=True,
    )
    data_coleta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_entrega_prevista: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_entrega_real: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    distancia_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    costs: Mapped[list["FreightCost"]] = relationship(
        back_populates="freight", cascade="all, delete-orphan", lazy="noload"
    )
    attachments: Mapped[list["FreightAttachment"]] = relationship(
        back_populates="freight", cascade="all, delete-orphan", lazy="noload"
    )
    tracking_updates: Mapped[list["TrackingUpdate"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="freight", cascade="all, delete-orphan", lazy="noload"
    )


class FreightCost(BaseModel):
    __tablename__ = "tm_freight_costs"

    freight_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tm_freights.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)

    freight: Mapped["Freight"] = relationship(back_populates="costs")


class FreightAttachment(BaseModel):
    __tablename__ = "tm_freight_attachments"

    freight_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tm_freights.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False, default="comprovante")
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)

    freight: Mapped["Freight"] = relationship(back_populates="attachments")
