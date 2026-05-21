"""Maintenance schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import MaintenanceStatus, MaintenanceType


class MaintenanceCreate(BaseModel):
    truck_id: uuid.UUID
    tipo: MaintenanceType
    descricao: str = Field(min_length=5)
    km_atual: float | None = Field(default=None, ge=0)
    km_proxima: float | None = Field(default=None, ge=0)
    custo: float | None = Field(default=None, ge=0)
    fornecedor: str | None = Field(default=None, max_length=200)
    data_inicio: datetime | None = None
    data_fim: datetime | None = None
    data_prevista: datetime | None = None
    status: MaintenanceStatus = MaintenanceStatus.AGENDADA
    observacoes: str | None = None


class MaintenanceUpdate(BaseModel):
    tipo: MaintenanceType | None = None
    descricao: str | None = Field(default=None, min_length=5)
    km_atual: float | None = Field(default=None, ge=0)
    km_proxima: float | None = Field(default=None, ge=0)
    custo: float | None = Field(default=None, ge=0)
    fornecedor: str | None = None
    data_inicio: datetime | None = None
    data_fim: datetime | None = None
    data_prevista: datetime | None = None
    status: MaintenanceStatus | None = None
    observacoes: str | None = None


class MaintenanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    truck_id: uuid.UUID
    tipo: MaintenanceType
    descricao: str
    km_atual: float | None
    km_proxima: float | None
    custo: float | None
    fornecedor: str | None
    data_inicio: datetime | None
    data_fim: datetime | None
    data_prevista: datetime | None
    status: MaintenanceStatus
    observacoes: str | None
    created_at: datetime
    updated_at: datetime


class MaintenanceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    truck_id: uuid.UUID
    tipo: MaintenanceType
    descricao: str
    custo: float | None
    status: MaintenanceStatus
    data_prevista: datetime | None
    created_at: datetime
