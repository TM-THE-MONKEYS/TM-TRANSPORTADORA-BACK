"""Fuel refill (abastecimento) schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.shared.utils.data_normalization import FUEL_CREATE_RULES, parse_decimal_br
from app.shared.utils.field_aliases import normalize_create_payload


FUEL_FIELD_ALIASES: dict[str, str] = {
    "freightId": "freight_id",
    "driverId": "driver_id",
    "truckId": "truck_id",
    "totalValue": "valor_total",
    "value": "valor_total",
    "valor": "valor_total",
    "amount": "valor_total",
    "liters": "litros",
    "liter": "litros",
    "pricePerLiter": "valor_litro",
    "price_per_liter": "valor_litro",
    "currentKm": "km_atual",
    "km": "km_atual",
    "gasStation": "posto",
    "station": "posto",
    "city": "cidade",
    "state": "estado",
    "notes": "observacoes",
    "refuelDate": "data_abastecimento",
    "refuel_at": "data_abastecimento",
}


class FuelRefillCreate(BaseModel):
    freight_id: uuid.UUID
    driver_id: uuid.UUID | None = None
    truck_id: uuid.UUID | None = None
    litros: float = Field(gt=0)
    valor_total: float = Field(gt=0)
    valor_litro: float | None = Field(default=None, gt=0)
    km_atual: float | None = Field(default=None, ge=0)
    posto: str | None = Field(default=None, max_length=150)
    cidade: str | None = Field(default=None, max_length=100)
    estado: str | None = Field(default=None, max_length=2)
    observacoes: str | None = None
    data_abastecimento: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: object) -> object:
        return normalize_create_payload(
            data,
            FUEL_FIELD_ALIASES,
            required=(),
            field_rules=FUEL_CREATE_RULES,
        )

    @field_validator("litros", "valor_total", "valor_litro", "km_atual", mode="before")
    @classmethod
    def normalize_decimals(cls, v: object) -> object:
        return parse_decimal_br(v) if v is not None else v


class FuelRefillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    freight_id: uuid.UUID
    driver_id: uuid.UUID
    truck_id: uuid.UUID | None
    registrado_por_user_id: uuid.UUID | None
    freight_cost_id: uuid.UUID | None
    litros: float
    valor_total: float
    valor_litro: float | None
    km_atual: float | None
    posto: str | None
    cidade: str | None
    estado: str | None
    observacoes: str | None
    data_abastecimento: datetime
    created_at: datetime
    freight_code: str | None = None
    driver_name: str | None = None
    truck_plate: str | None = None


class FuelRefillCreatedResponse(FuelRefillRead):
    notification_id: uuid.UUID | None = None


class FuelFreightSummary(BaseModel):
    freight_id: uuid.UUID
    freight_code: str
    status: str
    driver_id: uuid.UUID | None
    driver_name: str | None
    truck_id: uuid.UUID | None
    truck_plate: str | None
    total_litros: float
    total_valor: float
    refills_count: int


class ActiveFreightContext(BaseModel):
    """Frete em andamento do motorista logado (tela de abastecimento)."""

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
    """Frete elegível para abastecimento (exclui entregue, cancelado e orçamento)."""
