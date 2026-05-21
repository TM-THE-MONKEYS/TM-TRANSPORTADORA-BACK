"""Freight schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import FreightStatus


class AddressPoint(BaseModel):
    logradouro: str
    numero: str | None = None
    bairro: str | None = None
    cidade: str
    estado: str = Field(max_length=2)
    cep: str | None = None


class FreightCostCreate(BaseModel):
    tipo: str = Field(max_length=100)
    valor: float = Field(gt=0)
    descricao: str | None = None


class FreightCostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tipo: str
    valor: float
    descricao: str | None
    created_at: datetime


class FreightAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    file_url: str
    tipo: str
    descricao: str | None
    created_at: datetime


class FreightCreate(BaseModel):
    client_id: uuid.UUID
    driver_id: uuid.UUID | None = None
    truck_id: uuid.UUID | None = None
    origem: AddressPoint
    destino: AddressPoint
    valor_frete: float = Field(gt=0)
    status: FreightStatus = FreightStatus.ORCAMENTO
    data_coleta: datetime | None = None
    data_entrega_prevista: datetime | None = None
    distancia_km: float | None = Field(default=None, gt=0)
    observacoes: str | None = None
    costs: list[FreightCostCreate] = []


class FreightUpdate(BaseModel):
    driver_id: uuid.UUID | None = None
    truck_id: uuid.UUID | None = None
    valor_frete: float | None = Field(default=None, gt=0)
    status: FreightStatus | None = None
    data_coleta: datetime | None = None
    data_entrega_prevista: datetime | None = None
    data_entrega_real: datetime | None = None
    distancia_km: float | None = Field(default=None, gt=0)
    observacoes: str | None = None


class FreightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    driver_id: uuid.UUID | None
    truck_id: uuid.UUID | None
    origem: dict
    destino: dict
    valor_frete: float
    status: FreightStatus
    data_coleta: datetime | None
    data_entrega_prevista: datetime | None
    data_entrega_real: datetime | None
    distancia_km: float | None
    observacoes: str | None
    created_at: datetime
    updated_at: datetime


class FreightListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    driver_id: uuid.UUID | None
    truck_id: uuid.UUID | None
    valor_frete: float
    status: FreightStatus
    data_coleta: datetime | None
    created_at: datetime
