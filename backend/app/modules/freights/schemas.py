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


class FreightStatusUpdate(BaseModel):
    status: FreightStatus


# ── Frontend-compatible schemas ──────────────────────────────────────────────

class FreightFrontendRead(BaseModel):
    """Maps backend freight model to the frontend's FreightOrder interface."""

    id: uuid.UUID
    tenant_id: str = "default"
    branch_id: str | None = None
    code: str
    customer_id: uuid.UUID
    customer_name: str | None = None
    origin_city: str
    origin_state: str
    destination_city: str
    destination_state: str
    cargo_description: str
    weight_kg: float = 0.0
    value_brl: float
    freight_type: str = "carga_geral"
    status: FreightStatus
    deadline_at: str | None = None
    responsible_id: str | None = None
    truck_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, freight: object) -> "FreightFrontendRead":
        origem = freight.origem or {}  # type: ignore[attr-defined]
        destino = freight.destino or {}  # type: ignore[attr-defined]
        code = f"OF-{str(freight.id)[:8].upper()}"  # type: ignore[attr-defined]
        deadline = freight.data_entrega_prevista  # type: ignore[attr-defined]
        return cls(
            id=freight.id,  # type: ignore[attr-defined]
            code=code,
            customer_id=freight.client_id,  # type: ignore[attr-defined]
            origin_city=origem.get("cidade", ""),
            origin_state=origem.get("estado", ""),
            destination_city=destino.get("cidade", ""),
            destination_state=destino.get("estado", ""),
            cargo_description=freight.observacoes or "Carga não especificada",  # type: ignore[attr-defined]
            value_brl=freight.valor_frete,  # type: ignore[attr-defined]
            status=freight.status,  # type: ignore[attr-defined]
            deadline_at=deadline.isoformat() if deadline else None,
            truck_id=freight.truck_id,  # type: ignore[attr-defined]
            driver_id=freight.driver_id,  # type: ignore[attr-defined]
            created_at=freight.created_at.isoformat(),  # type: ignore[attr-defined]
            updated_at=freight.updated_at.isoformat(),  # type: ignore[attr-defined]
        )


class FreightFrontendListItem(BaseModel):
    id: uuid.UUID
    tenant_id: str = "default"
    code: str
    customer_id: uuid.UUID
    origin_city: str
    origin_state: str
    destination_city: str
    destination_state: str
    value_brl: float
    status: FreightStatus
    truck_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, freight: object) -> "FreightFrontendListItem":
        origem = freight.origem or {}  # type: ignore[attr-defined]
        destino = freight.destino or {}  # type: ignore[attr-defined]
        return cls(
            id=freight.id,  # type: ignore[attr-defined]
            code=f"OF-{str(freight.id)[:8].upper()}",  # type: ignore[attr-defined]
            customer_id=freight.client_id,  # type: ignore[attr-defined]
            origin_city=origem.get("cidade", ""),
            origin_state=origem.get("estado", ""),
            destination_city=destino.get("cidade", ""),
            destination_state=destino.get("estado", ""),
            value_brl=freight.valor_frete,  # type: ignore[attr-defined]
            status=freight.status,  # type: ignore[attr-defined]
            truck_id=freight.truck_id,  # type: ignore[attr-defined]
            driver_id=freight.driver_id,  # type: ignore[attr-defined]
            created_at=freight.created_at.isoformat(),  # type: ignore[attr-defined]
            updated_at=freight.updated_at.isoformat(),  # type: ignore[attr-defined]
        )
