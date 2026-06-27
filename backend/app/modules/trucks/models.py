"""Truck model."""
from __future__ import annotations

import uuid

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, SoftDeleteMixin, TenantMixin
from app.shared.enums import TruckStatus


class Truck(TenantMixin, SoftDeleteMixin, BaseModel):
    __tablename__ = "tm_trucks"

    placa: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    modelo: Mapped[str] = mapped_column(String(100), nullable=False)
    marca: Mapped[str] = mapped_column(String(100), nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    capacidade_kg: Mapped[float] = mapped_column(Float, nullable=False)
    consumo_km_l: Mapped[float | None] = mapped_column(Float, nullable=True)
    km_atual: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[TruckStatus] = mapped_column(
        Enum(TruckStatus, name="truckstatus", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TruckStatus.DISPONIVEL,
    )
    renavam: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    chassi: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)


class TruckImplement(TenantMixin, SoftDeleteMixin, BaseModel):
    __tablename__ = "tm_truck_implements"

    truck_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_trucks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    placa: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    identificador: Mapped[str | None] = mapped_column(String(50), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(100), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capacidade_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    width_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
