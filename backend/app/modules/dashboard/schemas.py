"""Dashboard KPI schemas."""
from __future__ import annotations

from pydantic import BaseModel


# ── Internal detailed schemas (used by service layer) ───────────────────────

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


# ── Frontend-compatible flat schema (matches Next.js DashboardKpis type) ────

class DashboardKPIsFrontend(BaseModel):
    """Flat KPI response matching the frontend's DashboardKpis interface."""

    freights_in_progress: int
    active_trucks: int
    available_drivers: int
    monthly_revenue_brl: float
    operational_costs_brl: float
    maintenance_alerts: int
    financial_pending: int

    @classmethod
    def from_detailed(cls, kpis: DashboardKPIs) -> "DashboardKPIsFrontend":
        return cls(
            freights_in_progress=(
                kpis.freights.confirmado
                + kpis.freights.em_coleta
                + kpis.freights.em_transporte
            ),
            active_trucks=kpis.fleet.disponivel + kpis.fleet.em_viagem,
            available_drivers=kpis.active_drivers,
            monthly_revenue_brl=kpis.finance.receita_total,
            operational_costs_brl=kpis.finance.despesa_total,
            maintenance_alerts=kpis.upcoming_maintenance_alerts,
            financial_pending=int(
                kpis.finance.receitas_pendentes + kpis.finance.despesas_pendentes
            ),
        )


# ── Additional dashboard response schemas ───────────────────────────────────

class FreightStatusCount(BaseModel):
    status: str
    count: int


class RevenuePoint(BaseModel):
    date: str
    revenue: float
