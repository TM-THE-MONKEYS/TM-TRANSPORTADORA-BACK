"""Freight schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.shared.enums import FreightStatus
from app.shared.utils.data_normalization import (
    ADDRESS_RULES,
    FREIGHT_COST_RULES,
    FREIGHT_CREATE_RULES,
    FREIGHT_UPDATE_RULES,
    apply_field_rules,
    parse_decimal_br,
)
from app.shared.utils.field_aliases import normalize_create_payload, normalize_update_payload


class AddressPoint(BaseModel):
    logradouro: str
    numero: str | None = None
    bairro: str | None = None
    cidade: str
    estado: str = Field(max_length=2)
    cep: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_address(cls, data: object) -> object:
        if isinstance(data, dict):
            apply_field_rules(data, ADDRESS_RULES)
        return data


class FreightStopCreate(BaseModel):
    ordem: int = Field(ge=1, le=20)
    cep: str | None = None
    logradouro: str | None = None
    bairro: str | None = None
    cidade: str
    estado: str = Field(min_length=2, max_length=2)
    observacoes: str | None = None
    peso_kg: float | None = Field(default=None, gt=0)

    @model_validator(mode="before")
    @classmethod
    def normalize_stop(cls, data: object) -> object:
        if isinstance(data, dict):
            apply_field_rules(data, ADDRESS_RULES)
        return data


class FreightStopRead(BaseModel):
    id: uuid.UUID
    sequence: int
    city: str
    state: str
    street: str | None = None
    neighborhood: str | None = None
    cep: str | None = None
    cargo_description: str | None = None
    weight_kg: float | None = None

    @classmethod
    def from_orm(cls, stop: object) -> "FreightStopRead":
        return cls(
            id=stop.id,  # type: ignore[attr-defined]
            sequence=stop.sequence,  # type: ignore[attr-defined]
            city=stop.city,  # type: ignore[attr-defined]
            state=stop.state,  # type: ignore[attr-defined]
            street=stop.street,  # type: ignore[attr-defined]
            neighborhood=stop.neighborhood,  # type: ignore[attr-defined]
            cep=stop.cep,  # type: ignore[attr-defined]
            cargo_description=stop.cargo_description,  # type: ignore[attr-defined]
            weight_kg=stop.weight_kg,  # type: ignore[attr-defined]
        )


class FreightCostCreate(BaseModel):
    tipo: str = Field(max_length=100)
    valor: float = Field(gt=0)
    descricao: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_cost(cls, data: object) -> object:
        if isinstance(data, dict):
            apply_field_rules(data, FREIGHT_COST_RULES)
        return data


class FreightCostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    freight_id: uuid.UUID
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
    paradas: list[FreightStopCreate] = []

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: object) -> object:
        normalized = normalize_create_payload(
            data,
            {},
            required=(),
            field_rules=FREIGHT_CREATE_RULES,
            nested_rules={"origem": ADDRESS_RULES, "destino": ADDRESS_RULES},
        )
        if isinstance(normalized, dict):
            costs = normalized.get("costs")
            if isinstance(costs, list):
                for cost in costs:
                    if isinstance(cost, dict):
                        apply_field_rules(cost, FREIGHT_COST_RULES)
            paradas = normalized.get("paradas")
            if isinstance(paradas, list):
                for parada in paradas:
                    if isinstance(parada, dict):
                        apply_field_rules(parada, ADDRESS_RULES)
        return normalized

    @model_validator(mode="after")
    def validate_paradas(self) -> "FreightCreate":
        if len(self.paradas) > 20:
            raise ValueError("Máximo de 20 paradas intermediárias por frete")
        ordens = [p.ordem for p in self.paradas]
        if len(ordens) != len(set(ordens)):
            raise ValueError("Ordem das paradas deve ser única por frete")
        expected = list(range(1, len(self.paradas) + 1))
        if sorted(ordens) != expected:
            raise ValueError("Ordem das paradas deve ser sequencial de 1 a N")
        return self

    @field_validator("valor_frete", "distancia_km", mode="before")
    @classmethod
    def normalize_decimal_fields(cls, v: object) -> object:
        return parse_decimal_br(v) if v is not None else v


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

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: object) -> object:
        return normalize_update_payload(data, {}, field_rules=FREIGHT_UPDATE_RULES)

    @field_validator("valor_frete", "distancia_km", mode="before")
    @classmethod
    def normalize_decimal_fields(cls, v: object) -> object:
        return parse_decimal_br(v) if v is not None else v


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
    origin_street: str | None = None
    origin_neighborhood: str | None = None
    origin_cep: str | None = None
    destination_city: str
    destination_state: str
    destination_street: str | None = None
    destination_neighborhood: str | None = None
    destination_cep: str | None = None
    stops: list[FreightStopRead] = []
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
        stops_raw = getattr(freight, "stops", None) or []
        stops = [FreightStopRead.from_orm(s) for s in sorted(stops_raw, key=lambda s: s.sequence)]
        return cls(
            id=freight.id,  # type: ignore[attr-defined]
            code=code,
            customer_id=freight.client_id,  # type: ignore[attr-defined]
            origin_city=origem.get("cidade", ""),
            origin_state=origem.get("estado", ""),
            origin_street=origem.get("logradouro"),
            origin_neighborhood=origem.get("bairro"),
            origin_cep=origem.get("cep"),
            destination_city=destino.get("cidade", ""),
            destination_state=destino.get("estado", ""),
            destination_street=destino.get("logradouro"),
            destination_neighborhood=destino.get("bairro"),
            destination_cep=destino.get("cep"),
            stops=stops,
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
    stops: list[FreightStopRead] = []
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
        stops_raw = getattr(freight, "stops", None) or []
        stops = [FreightStopRead.from_orm(s) for s in sorted(stops_raw, key=lambda s: s.sequence)]
        return cls(
            id=freight.id,  # type: ignore[attr-defined]
            code=f"OF-{str(freight.id)[:8].upper()}",  # type: ignore[attr-defined]
            customer_id=freight.client_id,  # type: ignore[attr-defined]
            origin_city=origem.get("cidade", ""),
            origin_state=origem.get("estado", ""),
            destination_city=destino.get("cidade", ""),
            destination_state=destino.get("estado", ""),
            stops=stops,
            value_brl=freight.valor_frete,  # type: ignore[attr-defined]
            status=freight.status,  # type: ignore[attr-defined]
            truck_id=freight.truck_id,  # type: ignore[attr-defined]
            driver_id=freight.driver_id,  # type: ignore[attr-defined]
            created_at=freight.created_at.isoformat(),  # type: ignore[attr-defined]
            updated_at=freight.updated_at.isoformat(),  # type: ignore[attr-defined]
        )
