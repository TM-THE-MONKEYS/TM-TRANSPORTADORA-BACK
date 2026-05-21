"""Finance schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import FinanceEntryStatus, FinanceEntryType


class FinanceEntryCreate(BaseModel):
    tipo: FinanceEntryType
    categoria: str = Field(min_length=1, max_length=100)
    descricao: str = Field(min_length=1)
    valor: float = Field(gt=0)
    freight_id: uuid.UUID | None = None
    data_vencimento: date | None = None
    data_pagamento: date | None = None
    status: FinanceEntryStatus = FinanceEntryStatus.PENDENTE
    observacoes: str | None = None


class FinanceEntryUpdate(BaseModel):
    categoria: str | None = Field(default=None, min_length=1, max_length=100)
    descricao: str | None = None
    valor: float | None = Field(default=None, gt=0)
    data_vencimento: date | None = None
    data_pagamento: date | None = None
    status: FinanceEntryStatus | None = None
    observacoes: str | None = None


class FinanceEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: FinanceEntryType
    categoria: str
    descricao: str
    valor: float
    freight_id: uuid.UUID | None
    data_vencimento: date | None
    data_pagamento: date | None
    status: FinanceEntryStatus
    observacoes: str | None
    created_at: datetime
    updated_at: datetime


class FinanceEntryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: FinanceEntryType
    categoria: str
    descricao: str
    valor: float
    status: FinanceEntryStatus
    data_vencimento: date | None
    created_at: datetime


class CashFlowResponse(BaseModel):
    total_receitas: float
    total_despesas: float
    saldo: float
    receitas_pendentes: float
    despesas_pendentes: float
    receitas_pagas: float
    despesas_pagas: float
