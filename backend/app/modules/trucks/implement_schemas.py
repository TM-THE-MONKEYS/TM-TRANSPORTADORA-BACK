"""Truck implement schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.shared.enums import ImplementType
from app.shared.utils.data_normalization import (
    IMPLEMENT_CREATE_RULES,
    IMPLEMENT_UPDATE_RULES,
    normalize_plate,
)
from app.shared.utils.field_aliases import (
    IMPLEMENT_CREATE_ALIASES,
    IMPLEMENT_UPDATE_ALIASES,
    normalize_create_payload,
    normalize_update_payload,
)


class TruckImplementCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    tipo: ImplementType
    placa: str | None = Field(default=None, min_length=7, max_length=10)
    identificador: str | None = Field(default=None, max_length=50)
    marca: str | None = Field(default=None, max_length=100)
    modelo: str | None = Field(default=None, max_length=100)
    capacidade_kg: float | None = Field(default=None, gt=0)
    observacoes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_frontend_aliases(cls, data: object) -> object:
        return normalize_create_payload(
            data,
            IMPLEMENT_CREATE_ALIASES,
            required=(("nome", "Nome"), ("tipo", "Tipo")),
            optional_nullable=(
                "placa",
                "identificador",
                "marca",
                "modelo",
                "capacidade_kg",
                "observacoes",
            ),
            field_rules=IMPLEMENT_CREATE_RULES,
        )

    @field_validator("placa", mode="before")
    @classmethod
    def normalize_placa_field(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return normalize_plate(v)

    @field_validator("capacidade_kg", mode="before")
    @classmethod
    def normalize_capacidade(cls, v: object) -> object:
        from app.shared.utils.data_normalization import parse_decimal_br

        return parse_decimal_br(v) if v is not None else v

    @model_validator(mode="after")
    def ensure_identifier(self) -> "TruckImplementCreate":
        if not self.identificador and self.placa:
            return self.model_copy(update={"identificador": self.placa})
        return self


class TruckImplementUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    tipo: ImplementType | None = None
    placa: str | None = Field(default=None, min_length=7, max_length=10)
    identificador: str | None = Field(default=None, max_length=50)
    marca: str | None = Field(default=None, max_length=100)
    modelo: str | None = Field(default=None, max_length=100)
    capacidade_kg: float | None = Field(default=None, gt=0)
    observacoes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_frontend_aliases(cls, data: object) -> object:
        return normalize_update_payload(
            data,
            IMPLEMENT_UPDATE_ALIASES,
            field_rules=IMPLEMENT_UPDATE_RULES,
        )

    @field_validator("placa", mode="before")
    @classmethod
    def normalize_placa_field(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return normalize_plate(v)

    @field_validator("capacidade_kg", mode="before")
    @classmethod
    def normalize_capacidade(cls, v: object) -> object:
        from app.shared.utils.data_normalization import parse_decimal_br

        return parse_decimal_br(v) if v is not None else v


class TruckImplementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    truck_id: uuid.UUID
    nome: str
    tipo: str
    placa: str | None
    identificador: str | None
    marca: str | None
    modelo: str | None
    capacidade_kg: float | None
    observacoes: str | None
    created_at: datetime
    updated_at: datetime


class TruckImplementFrontendRead(BaseModel):
    id: uuid.UUID
    truck_id: uuid.UUID
    tenant_id: str = "default"
    name: str
    type: str
    plate: str | None = None
    identifier: str | None = None
    brand: str | None = None
    model: str | None = None
    capacity_kg: float | None = None
    created_at: str

    @classmethod
    def from_orm(cls, implement: object) -> "TruckImplementFrontendRead":
        return cls(
            id=implement.id,  # type: ignore[attr-defined]
            truck_id=implement.truck_id,  # type: ignore[attr-defined]
            name=implement.nome,  # type: ignore[attr-defined]
            type=implement.tipo,  # type: ignore[attr-defined]
            plate=implement.placa,  # type: ignore[attr-defined]
            identifier=implement.identificador,  # type: ignore[attr-defined]
            brand=implement.marca,  # type: ignore[attr-defined]
            model=implement.modelo,  # type: ignore[attr-defined]
            capacity_kg=implement.capacidade_kg,  # type: ignore[attr-defined]
            created_at=implement.created_at.isoformat(),  # type: ignore[attr-defined]
        )
