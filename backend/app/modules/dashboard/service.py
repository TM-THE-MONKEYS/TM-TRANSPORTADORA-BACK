"""Dashboard service."""
from __future__ import annotations

import hashlib
import json
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
from app.modules.drivers.repository import DriverRepository
from app.modules.finance.models import FinanceEntry
from app.modules.finance.repository import FinanceRepository
from app.modules.freights.repository import FreightRepository
from app.modules.maintenance.repository import MaintenanceRepository
from app.modules.trucks.repository import TruckRepository
from app.modules.users.models import User
from app.shared.enums import FinanceEntryStatus, FinanceEntryType, UserRole
from app.shared.exceptions.custom import BadRequestException, ForbiddenException

log = structlog.get_logger(__name__)

_KPI_CACHE_TTL_SECONDS = 45


class DashboardService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    def _check_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR, UserRole.FINANCEIRO):
            raise ForbiddenException("Acesso negado ao dashboard")

    def _validate_period(
        self, period_from: date | None, period_to: date | None
    ) -> None:
        if (
            period_from is not None
            and period_to is not None
            and period_from > period_to
        ):
            raise BadRequestException(
                "period_from não pode ser posterior a period_to."
            )

    @staticmethod
    def _filters_hash(
        *,
        branch_id: uuid.UUID | None,
        client_id: uuid.UUID | None,
        truck_id: uuid.UUID | None,
        driver_id: uuid.UUID | None,
        period_from: date | None,
        period_to: date | None,
    ) -> str:
        payload = {
            "branch_id": str(branch_id) if branch_id else None,
            "client_id": str(client_id) if client_id else None,
            "truck_id": str(truck_id) if truck_id else None,
            "driver_id": str(driver_id) if driver_id else None,
            "period_from": period_from.isoformat() if period_from else None,
            "period_to": period_to.isoformat() if period_to else None,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _kpi_cache_key(
        self,
        *,
        competencia_mes: int | None,
        competencia_ano: int | None,
        branch_id: uuid.UUID | None,
        client_id: uuid.UUID | None,
        truck_id: uuid.UUID | None,
        driver_id: uuid.UUID | None,
        period_from: date | None,
        period_to: date | None,
    ) -> str:
        filters_hash = self._filters_hash(
            branch_id=branch_id,
            client_id=client_id,
            truck_id=truck_id,
            driver_id=driver_id,
            period_from=period_from,
            period_to=period_to,
        )
        return (
            f"dash:kpis:{self._tenant_id}:"
            f"{competencia_mes}:{competencia_ano}:{filters_hash}"
        )

    async def _get_detailed_kpis(
        self,
        requesting_user: User,
        *,
        branch_id: uuid.UUID | None = None,
        client_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        period_from: date | None = None,
        period_to: date | None = None,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
    ) -> DashboardKPIs:
        self._check_access(requesting_user)
        self._validate_period(period_from, period_to)
        # branch_id aceito para compatibilidade com o client; não há coluna
        # (branches deferred). Isolamento já é por tenant_id.
        _ = branch_id

        freight_scope = {
            "client_id": client_id,
            "driver_id": driver_id,
            "truck_id": truck_id,
            "competencia_mes": competencia_mes,
            "competencia_ano": competencia_ano,
            "period_from": period_from,
            "period_to": period_to,
        }

        # Sempre sequencial na mesma AsyncSession.
        # asyncio.gather + sessões irmãs quebra no pooler Supabase (NullPool /
        # PgBouncer) → SQLAlchemyError → 503 em /dashboard/kpis.
        truck_repo = TruckRepository(self._session, self._tenant_id)
        freight_repo = FreightRepository(self._session, self._tenant_id)
        finance_repo = FinanceRepository(self._session, self._tenant_id)
        maintenance_repo = MaintenanceRepository(self._session, self._tenant_id)
        driver_repo = DriverRepository(self._session, self._tenant_id)

        truck_counts = await truck_repo.count_by_status()
        freight_counts = await freight_repo.count_by_status(**freight_scope)
        cash_flow = await finance_repo.get_cash_flow_summary(
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
            truck_id=truck_id,
            driver_id=driver_id,
            client_id=client_id,
            period_from=period_from,
            period_to=period_to,
        )
        maintenance_alerts = await maintenance_repo.count_upcoming_alerts(
            days_ahead=30, truck_id=truck_id
        )
        active_trucks = await truck_repo.count_operational(
            truck_id=truck_id,
            driver_id=driver_id,
            client_id=client_id,
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
            period_from=period_from,
            period_to=period_to,
        )
        active_drivers = await driver_repo.count_active(
            driver_id=driver_id,
            truck_id=truck_id,
            client_id=client_id,
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
            period_from=period_from,
            period_to=period_to,
        )

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
            upcoming_maintenance_alerts=maintenance_alerts,
            active_trucks=active_trucks,
        )

    async def get_kpis(
        self,
        requesting_user: User,
        *,
        branch_id: uuid.UUID | None = None,
        client_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        period_from: date | None = None,
        period_to: date | None = None,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
    ) -> DashboardKPIsFrontend:
        """Return flat KPIs matching the frontend DashboardKpis interface."""
        self._check_access(requesting_user)
        self._validate_period(period_from, period_to)

        cache_key = self._kpi_cache_key(
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
            branch_id=branch_id,
            client_id=client_id,
            truck_id=truck_id,
            driver_id=driver_id,
            period_from=period_from,
            period_to=period_to,
        )

        try:
            from app.core.database.redis import get_redis

            redis = get_redis()
            cached = await redis.get(cache_key)
            if cached:
                log.debug("dashboard_kpis_cache_hit", cache_key=cache_key)
                return DashboardKPIsFrontend.model_validate_json(cached)
        except Exception:
            log.warning(
                "dashboard_kpis_cache_unavailable",
                cache_key=cache_key,
                exc_info=True,
            )

        detailed = await self._get_detailed_kpis(
            requesting_user,
            branch_id=branch_id,
            client_id=client_id,
            truck_id=truck_id,
            driver_id=driver_id,
            period_from=period_from,
            period_to=period_to,
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
        )
        frontend = DashboardKPIsFrontend.from_detailed(detailed)

        try:
            from app.core.database.redis import get_redis

            redis = get_redis()
            await redis.setex(
                cache_key,
                _KPI_CACHE_TTL_SECONDS,
                frontend.model_dump_json(),
            )
        except Exception:
            log.warning(
                "dashboard_kpis_cache_set_failed",
                cache_key=cache_key,
                exc_info=True,
            )

        return frontend

    async def get_freights_by_status(
        self,
        requesting_user: User,
        *,
        branch_id: uuid.UUID | None = None,
        client_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        period_from: date | None = None,
        period_to: date | None = None,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
    ) -> list[FreightStatusCount]:
        self._check_access(requesting_user)
        self._validate_period(period_from, period_to)
        _ = branch_id
        freight_repo = FreightRepository(self._session, self._tenant_id)
        counts = await freight_repo.count_by_status(
            client_id=client_id,
            driver_id=driver_id,
            truck_id=truck_id,
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
            period_from=period_from,
            period_to=period_to,
        )
        return [
            FreightStatusCount(status=status, count=count)
            for status, count in counts.items()
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
                FinanceEntry.tenant_id == self._tenant_id,
            )
            .group_by(func.date(FinanceEntry.created_at))
            .order_by(func.date(FinanceEntry.created_at))
        )

        return [
            RevenuePoint(date=str(row.day), revenue=float(row.revenue or 0))
            for row in result.all()
        ]
