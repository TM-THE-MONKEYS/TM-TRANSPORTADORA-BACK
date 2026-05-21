"""Truck model."""
from __future__ import annotations

from sqlalchemy import Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, SoftDeleteMixin
from app.shared.enums import TruckStatus


class Truck(SoftDeleteMixin, BaseModel):
    __tablename__ = "tm_trucks"

    placa: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    modelo: Mapped[str] = mapped_column(String(100), nullable=False)
    marca: Mapped[str] = mapped_column(String(100), nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    capacidade_kg: Mapped[float] = mapped_column(Float, nullable=False)
    consumo_km_l: Mapped[float | None] = mapped_column(Float, nullable=True)
    km_atual: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[TruckStatus] = mapped_column(
        Enum(TruckStatus, name="truckstatus", create_type=True),
        nullable=False,
        default=TruckStatus.DISPONIVEL,
    )
    renavam: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    chassi: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
