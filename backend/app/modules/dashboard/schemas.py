"""Dashboard KPI schemas."""
from __future__ import annotations

from pydantic import BaseModel


class FleetSummary(BaseModel):
    total: int
    disponivel: int
    em_viagem: int
    em_manutencao: int
    inativo: int


class FreightSummary(BaseModel):
    total: int
    orcamento: int
    confirmado: int
    em_coleta: int
    em_transporte: int
    entregue: int
    cancelado: int


class FinanceSummary(BaseModel):
    receita_total: float
    despesa_total: float
    saldo: float
    receitas_pendentes: float
    despesas_pendentes: float


class DashboardKPIs(BaseModel):
    fleet: FleetSummary
    freights: FreightSummary
    finance: FinanceSummary
    active_drivers: int
    upcoming_maintenance_alerts: int
