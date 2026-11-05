"""Dashboard service."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import structlog
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
from app.modules.drivers.repository import DriverRepository
from app.modules.finance.models import FinanceEntry
from app.modules.finance.repository import FinanceRepository
from app.modules.freights.models import Freight
from app.modules.freights.repository import FreightRepository
from app.modules.maintenance.repository import MaintenanceRepository
from app.modules.trucks.repository import TruckRepository
from app.modules.users.models import User
from app.shared.enums import (
    DriverStatus,
    FinanceEntryStatus,
    FinanceEntryType,
    FreightStatus,
    UserRole,
)
from app.shared.exceptions.custom import ForbiddenException
from app.shared.filters.competencia import freight_competencia_filter_clause

log = structlog.get_logger(__name__)


class DashboardService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    def _check_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR, UserRole.FINANCEIRO):
            raise ForbiddenException("Acesso negado ao dashboard")

    async def _get_detailed_kpis(self, requesting_user: User) -> DashboardKPIs:
        self._check_access(requesting_user)

        truck_repo = TruckRepository(self._session, self._tenant_id)
        freight_repo = FreightRepository(self._session, self._tenant_id)
        finance_repo = FinanceRepository(self._session, self._tenant_id)
        maintenance_repo = MaintenanceRepository(self._session, self._tenant_id)
        driver_repo = DriverRepository(self._session, self._tenant_id)

        truck_counts = await truck_repo.count_by_status()
        freight_counts = await freight_repo.count_by_status()
        cash_flow = await finance_repo.get_cash_flow_summary()
        maintenance_alerts = await maintenance_repo.get_upcoming_alerts(days_ahead=30)
        cnh_alerts = await driver_repo.count_cnh_alerts(days_ahead=30)

        active_drivers_result = await self._session.execute(
            select(func.count(Driver.id)).where(
                Driver.deleted_at.is_(None),
                Driver.status == DriverStatus.ATIVO,
                Driver.tenant_id == self._tenant_id,
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
            cnh_alerts=cnh_alerts,
        )

    async def get_kpis(
        self,
        requesting_user: User,
        *,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
        driver_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
        client_id: uuid.UUID | None = None,
    ) -> DashboardKPIsFrontend:
        """Return flat KPIs matching the frontend DashboardKpis interface.

        Os filtros opcionais valem só para entregas no prazo. Os demais KPIs
        seguem o comportamento anterior (sem esses filtros).
        """
        detailed = await self._get_detailed_kpis(requesting_user)
        on_time, evaluated = await self._count_on_time_deliveries(
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
            driver_id=driver_id,
            truck_id=truck_id,
            client_id=client_id,
        )
        detailed.on_time_deliveries = on_time
        detailed.deliveries_with_deadline = evaluated
        return DashboardKPIsFrontend.from_detailed(detailed)

    async def _count_on_time_deliveries(
        self,
        *,
        competencia_mes: int | None,
        competencia_ano: int | None,
        driver_id: uuid.UUID | None,
        truck_id: uuid.UUID | None,
        client_id: uuid.UUID | None,
    ) -> tuple[int, int]:
        """Entregas com as duas datas, e quantas chegaram até o prazo.

        Compara os instantes gravados. data_entrega_prevista de dia inteiro
        fica ao meio-dia de São Paulo.
        """
        filters = [
            Freight.deleted_at.is_(None),
            Freight.tenant_id == self._tenant_id,
            Freight.status == FreightStatus.ENTREGUE,
            Freight.data_entrega_real.is_not(None),
            Freight.data_entrega_prevista.is_not(None),
        ]
        if competencia_mes and competencia_ano:
            filters.append(
                freight_competencia_filter_clause(competencia_ano, competencia_mes)
            )
        if driver_id:
            filters.append(Freight.driver_id == driver_id)
        if truck_id:
            filters.append(Freight.truck_id == truck_id)
        if client_id:
            filters.append(Freight.client_id == client_id)

        evaluated = await self._session.execute(
            select(func.count(Freight.id)).where(*filters)
        )
        on_time = await self._session.execute(
            select(func.count(Freight.id)).where(
                *filters,
                Freight.data_entrega_real <= Freight.data_entrega_prevista,
            )
        )
        return int(on_time.scalar_one()), int(evaluated.scalar_one())

    async def get_freights_by_status(self, requesting_user: User) -> list[FreightStatusCount]:
        self._check_access(requesting_user)
        result = await self._session.execute(
            select(Freight.status, func.count(Freight.id).label("count"))
            .where(Freight.deleted_at.is_(None), Freight.tenant_id == self._tenant_id)
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
                FinanceEntry.data_pagamento.label("day"),
                func.sum(FinanceEntry.valor).label("revenue"),
            )
            .where(
                FinanceEntry.deleted_at.is_(None),
                FinanceEntry.tipo == FinanceEntryType.RECEITA,
                FinanceEntry.status == FinanceEntryStatus.PAGO,
                FinanceEntry.data_pagamento.is_not(None),
                FinanceEntry.data_pagamento >= since,
                FinanceEntry.tenant_id == self._tenant_id,
            )
            .group_by(FinanceEntry.data_pagamento)
            .order_by(FinanceEntry.data_pagamento)
        )

        return [
            RevenuePoint(date=str(row.day), revenue=float(row.revenue or 0))
            for row in result.all()
        ]
