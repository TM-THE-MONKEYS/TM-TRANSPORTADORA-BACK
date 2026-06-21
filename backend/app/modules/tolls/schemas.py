"""Toll charge (pedágio) schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.shared.utils.data_normalization import TOLL_CREATE_RULES, parse_decimal_br
from app.shared.utils.field_aliases import normalize_create_payload


TOLL_FIELD_ALIASES: dict[str, str] = {
    "freightId": "freight_id",
    "driverId": "driver_id",
    "value": "valor",
    "amount": "valor",
    "tollValue": "valor",
    "count": "quantidade",
    "tollCount": "quantidade",
    "plaza": "praca",
    "tollPlaza": "praca",
    "highway": "rodovia",
    "city": "cidade",
    "state": "estado",
    "notes": "observacoes",
    "tollDate": "data_pedagio",
    "toll_at": "data_pedagio",
}


class TollChargeCreate(BaseModel):
    freight_id: uuid.UUID
    driver_id: uuid.UUID | None = None
    valor: float = Field(gt=0)
    quantidade: int = Field(default=1, ge=1)
    praca: str | None = Field(default=None, max_length=150)
    rodovia: str | None = Field(default=None, max_length=100)
    cidade: str | None = Field(default=None, max_length=100)
    estado: str | None = Field(default=None, max_length=2)
    observacoes: str | None = None
    data_pedagio: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: object) -> object:
        return normalize_create_payload(
            data,
            TOLL_FIELD_ALIASES,
            required=(),
            field_rules=TOLL_CREATE_RULES,
        )

    @field_validator("valor", mode="before")
    @classmethod
    def normalize_decimal(cls, v: object) -> object:
        return parse_decimal_br(v) if v is not None else v


class TollChargeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    freight_id: uuid.UUID
    driver_id: uuid.UUID | None
    registrado_por_user_id: uuid.UUID | None
    freight_cost_id: uuid.UUID | None
    valor: float
    quantidade: int
    praca: str | None
    rodovia: str | None
    cidade: str | None
    estado: str | None
    observacoes: str | None
    data_pedagio: datetime
    created_at: datetime
    freight_code: str | None = None
    driver_name: str | None = None


class TollChargeCreatedResponse(TollChargeRead):
    notification_id: uuid.UUID | None = None


class TollFreightSummary(BaseModel):
    freight_id: uuid.UUID
    freight_code: str
    status: str
    driver_id: uuid.UUID | None
    driver_name: str | None
    total_valor: float
    total_quantidade: int
    charges_count: int


class ActiveFreightContext(BaseModel):
    """Frete em andamento do motorista logado (tela de pedágio)."""

    freight_id: uuid.UUID
    freight_code: str
    status: str
    driver_id: uuid.UUID
    driver_name: str
    truck_id: uuid.UUID | None
    truck_plate: str | None
    origin_city: str
    origin_state: str
    destination_city: str
    destination_state: str


class EligibleFreightItem(ActiveFreightContext):
    """Frete elegível para registro de pedágio."""
