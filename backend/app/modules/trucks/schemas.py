"""Truck schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.enums import TruckStatus


class TruckCreate(BaseModel):
    placa: str = Field(min_length=7, max_length=10)
    modelo: str = Field(min_length=1, max_length=100)
    marca: str = Field(min_length=1, max_length=100)
    ano: int = Field(ge=1950, le=2030)
    capacidade_kg: float = Field(gt=0)
    consumo_km_l: float | None = Field(default=None, gt=0)
    km_atual: float = Field(default=0.0, ge=0)
    status: TruckStatus = TruckStatus.DISPONIVEL
    renavam: str | None = Field(default=None, max_length=20)
    chassi: str | None = Field(default=None, max_length=50)
    cor: str | None = Field(default=None, max_length=50)
    observacoes: str | None = None

    @field_validator("placa")
    @classmethod
    def normalize_placa(cls, v: str) -> str:
        return v.upper().strip().replace("-", "").replace(" ", "")


class TruckUpdate(BaseModel):
    modelo: str | None = Field(default=None, min_length=1, max_length=100)
    marca: str | None = Field(default=None, min_length=1, max_length=100)
    capacidade_kg: float | None = Field(default=None, gt=0)
    consumo_km_l: float | None = Field(default=None, gt=0)
    km_atual: float | None = Field(default=None, ge=0)
    status: TruckStatus | None = None
    cor: str | None = None
    observacoes: str | None = None


class TruckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    placa: str
    modelo: str
    marca: str
    ano: int
    capacidade_kg: float
    consumo_km_l: float | None
    km_atual: float
    status: TruckStatus
    renavam: str | None
    chassi: str | None
    cor: str | None
    observacoes: str | None
    created_at: datetime
    updated_at: datetime


class TruckListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    placa: str
    modelo: str
    marca: str
    ano: int
    capacidade_kg: float
    km_atual: float
    status: TruckStatus
    created_at: datetime
