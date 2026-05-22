"""Maintenance model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, SoftDeleteMixin
from app.shared.enums import MaintenanceStatus, MaintenanceType


class Maintenance(SoftDeleteMixin, BaseModel):
    __tablename__ = "tm_maintenance"

    truck_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tm_trucks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[MaintenanceType] = mapped_column(
        Enum(MaintenanceType, name="maintenancetype", create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    km_atual: Mapped[float | None] = mapped_column(Float, nullable=True)
    km_proxima: Mapped[float | None] = mapped_column(Float, nullable=True)
    custo: Mapped[float | None] = mapped_column(Float, nullable=True)
    fornecedor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    data_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_prevista: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[MaintenanceStatus] = mapped_column(
        Enum(MaintenanceStatus, name="maintenancestatus", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=MaintenanceStatus.AGENDADA,
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
