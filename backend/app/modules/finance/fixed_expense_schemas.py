"""Schemas for fixed expenses."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.enums import FixedExpenseFrequency
from app.shared.utils.data_normalization import parse_decimal_br


class FixedExpenseCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    categoria: str = Field(min_length=1, max_length=100)
    valor: float = Field(gt=0)
    frequencia: FixedExpenseFrequency = FixedExpenseFrequency.MENSAL
    dia_vencimento: int | None = Field(default=None, ge=1, le=31)
    total_parcelas: int | None = Field(default=None, ge=1)
    parcelas_lancadas: int = Field(default=0, ge=0)
    data_inicio: date | None = None
    ativo: bool = True
    observacao: str | None = None

    @field_validator("valor", mode="before")
    @classmethod
    def normalize_valor(cls, v: object) -> object:
        return parse_decimal_br(v) if v is not None else v

    @field_validator("data_inicio", mode="before")
    @classmethod
    def normalize_data_inicio(cls, v: object) -> object:
        if isinstance(v, str) and "T" in v:
            return v.split("T")[0]
        return v


class FixedExpenseUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    categoria: str | None = Field(default=None, min_length=1, max_length=100)
    valor: float | None = Field(default=None, gt=0)
    frequencia: FixedExpenseFrequency | None = None
    dia_vencimento: int | None = Field(default=None, ge=1, le=31)
    total_parcelas: int | None = Field(default=None, ge=1)
    parcelas_lancadas: int | None = Field(default=None, ge=0)
    data_inicio: date | None = None
    ativo: bool | None = None
    observacao: str | None = None

    @field_validator("valor", mode="before")
    @classmethod
    def normalize_valor(cls, v: object) -> object:
        return parse_decimal_br(v) if v is not None else v

    @field_validator("data_inicio", mode="before")
    @classmethod
    def normalize_data_inicio(cls, v: object) -> object:
        if isinstance(v, str) and "T" in v:
            return v.split("T")[0]
        return v


class FixedExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    categoria: str
    valor: float
    frequencia: FixedExpenseFrequency
    dia_vencimento: int | None
    total_parcelas: int | None
    parcelas_lancadas: int
    data_inicio: date | None
    ativo: bool
    observacao: str | None
    created_at: datetime
    updated_at: datetime
