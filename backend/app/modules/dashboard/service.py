"""Dashboard service."""
from __future__ import annotations

import structlog
from datetime import date, timedelta
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dashboard.schemas import (
    DashboardKPIs,
    DashboardKPIsFrontend,
    FinanceSummary,
    FleetSummary,
    FreightStatusCount,
    FreightSummary,
    RevenuePoint,
)
from app.modules.drivers.models import Driver
from app.modules.finance.models import FinanceEntry
from app.modules.finance.repository import FinanceRepository
from app.modules.freights.models import Freight
from app.modules.freights.repository import FreightRepository
from app.modules.maintenance.repository import MaintenanceRepository
from app.modules.trucks.repository import TruckRepository
from app.modules.users.models import User
from app.shared.enums import DriverStatus, FinanceEntryStatus, FinanceEntryType, FreightStatus, UserRole
from app.shared.exceptions.custom import ForbiddenException

log = structlog.get_logger(__name__)


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _check_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR, UserRole.FINANCEIRO):
            raise ForbiddenException("Acesso negado ao dashboard")

    async def _get_detailed_kpis(self, requesting_user: User) -> DashboardKPIs:
        self._check_access(requesting_user)

        truck_repo = TruckRepository(self._session)
        freight_repo = FreightRepository(self._session)
        finance_repo = FinanceRepository(self._session)
        maintenance_repo = MaintenanceRepository(self._session)

        truck_counts = await truck_repo.count_by_status()
        freight_counts = await freight_repo.count_by_status()
        cash_flow = await finance_repo.get_cash_flow_summary()
        maintenance_alerts = await maintenance_repo.get_upcoming_alerts(days_ahead=30)

        active_drivers_result = await self._session.execute(
            select(func.count(Driver.id)).where(
                Driver.deleted_at.is_(None),
                Driver.status == DriverStatus.ATIVO,
            )
        )
        active_drivers = active_drivers_result.scalar_one()

        fleet = FleetSummary(
            total=sum(truck_counts.values()),
            disponivel=truck_counts.get("disponivel", 0),
            em_viagem=truck_counts.get("em_viagem", 0),
            em_manutencao=truck_counts.get("em_manutencao", 0),
            inativo=truck_counts.get("inativo", 0),
        )

        freights = FreightSummary(
            total=sum(freight_counts.values()),
            orcamento=freight_counts.get("orcamento", 0),
            confirmado=freight_counts.get("confirmado", 0),
            em_coleta=freight_counts.get("em_coleta", 0),
            em_transporte=freight_counts.get("em_transporte", 0),
            entregue=freight_counts.get("entregue", 0),
            cancelado=freight_counts.get("cancelado", 0),
        )

        finance = FinanceSummary(
            receita_total=cash_flow["total_receitas"],
            despesa_total=cash_flow["total_despesas"],
            saldo=cash_flow["saldo"],
            receitas_pendentes=cash_flow["receitas_pendentes"],
            despesas_pendentes=cash_flow["despesas_pendentes"],
        )

        return DashboardKPIs(
            fleet=fleet,
            freights=freights,
            finance=finance,
            active_drivers=active_drivers,
            upcoming_maintenance_alerts=len(maintenance_alerts),
        )

    async def get_kpis(self, requesting_user: User) -> DashboardKPIsFrontend:
        """Return flat KPIs matching the frontend DashboardKpis interface."""
        detailed = await self._get_detailed_kpis(requesting_user)
        return DashboardKPIsFrontend.from_detailed(detailed)

    async def get_freights_by_status(self, requesting_user: User) -> list[FreightStatusCount]:
        self._check_access(requesting_user)
        result = await self._session.execute(
            select(Freight.status, func.count(Freight.id).label("count"))
            .where(Freight.deleted_at.is_(None))
            .group_by(Freight.status)
        )
        return [
            FreightStatusCount(status=row.status, count=row.count)
            for row in result.all()
        ]

    async def get_revenue_series(
        self, requesting_user: User, days: int = 30
    ) -> list[RevenuePoint]:
        self._check_access(requesting_user)
        since = date.today() - timedelta(days=days)

        result = await self._session.execute(
            select(
                func.date(FinanceEntry.created_at).label("day"),
                func.sum(FinanceEntry.valor).label("revenue"),
            )
            .where(
                FinanceEntry.deleted_at.is_(None),
                FinanceEntry.tipo == FinanceEntryType.RECEITA,
                FinanceEntry.status == FinanceEntryStatus.PAGO,
                func.date(FinanceEntry.created_at) >= since,
            )
            .group_by(func.date(FinanceEntry.created_at))
            .order_by(func.date(FinanceEntry.created_at))
        )

        return [
            RevenuePoint(date=str(row.day), revenue=float(row.revenue or 0))
            for row in result.all()
        ]
