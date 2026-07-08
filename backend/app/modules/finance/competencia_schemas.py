"""Schemas for competência report and fixed expense launch status."""
from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from app.modules.finance.schemas import CashFlowResponse


class DailyCompetenciaPoint(BaseModel):
    date: str
    receitas: float
    despesas: float


class CategoryAmount(BaseModel):
    categoria: str
    valor: float


class CompetenciaReportResponse(BaseModel):
    competencia_mes: int
    competencia_ano: int
    cash_flow: CashFlowResponse
    daily_series: list[DailyCompetenciaPoint]
    expenses_by_category: list[CategoryAmount]


class FixedExpenseLaunchStatusItem(BaseModel):
    id: uuid.UUID
    nome: str
    categoria: str
    valor: float
    ativo: bool
    launched_this_month: bool
    linked_entry_id: uuid.UUID | None
    suggested_vencimento: date | None


class LaunchPendingResponse(BaseModel):
    launched_count: int
    skipped_count: int
