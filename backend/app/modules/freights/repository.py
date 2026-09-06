"""Freight repository."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import structlog
from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.modules.freights.models import (
    Freight,
    FreightAttachment,
    FreightCost,
    FreightStop,
)
from app.shared.base_repository import TenantBaseRepository
from app.shared.enums import FinanceEntryStatus, FinanceEntryType, FreightStatus
from app.shared.filters.competencia import (
    freight_competencia_filter_clause,
    freight_period_filter_clause,
)
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class FreightRepository(TenantBaseRepository[Freight]):
    model = Freight

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def get_by_id(
        self,
        freight_id: uuid.UUID,
        with_relations: bool = False,
        *,
        for_update: bool = False,
    ) -> Freight | None:
        query = self._base_query().where(Freight.id == freight_id)
        if for_update:
            query = query.with_for_update()
        if with_relations:
            query = query.options(
                selectinload(Freight.costs),
                selectinload(Freight.attachments),
                selectinload(Freight.stops),
            )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    def _apply_scope(
        self,
        query: Select,
        *,
        status: FreightStatus | None = None,
        client_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
        period_from: date | None = None,
        period_to: date | None = None,
        search: str | None = None,
    ) -> Select:
        if status:
            query = query.where(Freight.status == status)
        if client_id:
            query = query.where(Freight.client_id == client_id)
        if driver_id:
            query = query.where(Freight.driver_id == driver_id)
        if truck_id:
            query = query.where(Freight.truck_id == truck_id)
        if competencia_mes is not None and competencia_ano is not None:
            query = query.where(
                freight_competencia_filter_clause(competencia_ano, competencia_mes)
            )
        elif period_from is not None or period_to is not None:
            query = query.where(
                freight_period_filter_clause(period_from, period_to)
            )
        if search:
            query = self._apply_search(query, search)
        return query

    def _apply_search(self, query: Select, search: str) -> Select:
        from app.modules.clients.models import Client  # noqa: PLC0415

        raw = search.strip()
        if not raw:
            return query
        term = f"%{raw}%"
        id_term = raw[3:] if raw.upper().startswith("OF-") else raw
        id_like = f"%{id_term}%"
        stop_exists = exists().where(
            FreightStop.freight_id == Freight.id,
            FreightStop.city.ilike(term),
        )
        return query.outerjoin(Client, Freight.client_id == Client.id).where(
            or_(
                Client.nome.ilike(term),
                cast(Freight.origem, String).ilike(term),
                cast(Freight.destino, String).ilike(term),
                cast(Freight.id, String).ilike(id_like),
                Freight.observacoes.ilike(term),
                stop_exists,
            )
        )

    async def list(
        self,
        params: PageParams,
        status: FreightStatus | None = None,
        client_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
        search: str | None = None,
    ) -> tuple[list[Freight], int]:
        query = self._apply_scope(
            self._base_query(),
            status=status,
            client_id=client_id,
            driver_id=driver_id,
            truck_id=truck_id,
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
            search=search,
        )
        total = await self._count(query)
        result = await self._session.execute(
            query.options(selectinload(Freight.stops))
            .order_by(Freight.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
        return list(result.scalars().all()), total

    async def get_summary(
        self,
        status: FreightStatus | None = None,
        driver_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
    ) -> dict[str, float | int]:
        """Resumo agregado para cards de Fretes / Frota / Motoristas."""
        from app.modules.finance.models import FinanceEntry  # noqa: PLC0415

        # Predicados comuns para filtrar os fretes
        freight_filters = [
            Freight.deleted_at.is_(None),
            Freight.tenant_id == self._tenant_id,
        ]
        if status:
            freight_filters.append(Freight.status == status)
        if driver_id:
            freight_filters.append(Freight.driver_id == driver_id)
        if truck_id:
            freight_filters.append(Freight.truck_id == truck_id)
        if competencia_mes is not None and competencia_ano is not None:
            freight_filters.append(
                freight_competencia_filter_clause(competencia_ano, competencia_mes)
            )

        now_utc = datetime.now(timezone.utc)
        is_overdue = (
            Freight.data_entrega_prevista.isnot(None)
            & (Freight.data_entrega_prevista < now_utc)
            & Freight.status.notin_([FreightStatus.ENTREGUE, FreightStatus.CANCELADO])
        )

        # Query 1: agregados dos fretes (count, faturamento, atrasos)
        q1 = select(
            func.count(Freight.id).label("quantidade_fretes"),
            func.coalesce(func.sum(Freight.valor_frete), 0.0).label("faturamento_bruto"),
            func.count(Freight.id).filter(is_overdue).label("com_atraso"),
        ).where(*freight_filters)

        r1 = (await self._session.execute(q1)).one()

        # Query 2: gastos via FinanceEntry vinculados aos fretes filtrados
        q2 = (
            select(func.coalesce(func.sum(FinanceEntry.valor), 0.0).label("gastos"))
            .join(Freight, FinanceEntry.freight_id == Freight.id)
            .where(
                FinanceEntry.deleted_at.is_(None),
                FinanceEntry.tenant_id == self._tenant_id,
                FinanceEntry.tipo == FinanceEntryType.DESPESA,
                FinanceEntry.status != FinanceEntryStatus.CANCELADO,
                *freight_filters,
            )
        )
        r2 = (await self._session.execute(q2)).one()

        faturamento = float(r1.faturamento_bruto)
        gastos = float(r2.gastos)
        return {
            "faturamento_bruto": faturamento,
            "gastos": gastos,
            "margem": faturamento - gastos,
            "quantidade_fretes": int(r1.quantidade_fretes),
            "com_atraso": int(r1.com_atraso or 0),
        }

    async def list_costs_by_freight(self, freight_id: uuid.UUID) -> list[FreightCost]:
        result = await self._session.execute(
            select(FreightCost)
            .where(
                FreightCost.freight_id == freight_id,
                FreightCost.tenant_id == self._tenant_id,
            )
            .order_by(FreightCost.created_at.desc())
        )
        return list(result.scalars().all())

    async def add_stops(self, freight_id: uuid.UUID, stops: list[FreightStop]) -> list[FreightStop]:
        for stop in stops:
            stop.freight_id = freight_id
            stop.tenant_id = self._tenant_id
            self._session.add(stop)
        await self._session.flush()
        return stops

    async def add_cost(self, freight_id: uuid.UUID, tipo: str, valor: float, descricao: str | None = None) -> FreightCost:
        cost = FreightCost(freight_id=freight_id, tipo=tipo, valor=valor, descricao=descricao, tenant_id=self._tenant_id)
        self._session.add(cost)
        await self._session.flush()
        return cost

    async def add_attachment(self, freight_id: uuid.UUID, file_url: str, tipo: str, descricao: str | None) -> FreightAttachment:
        att = FreightAttachment(freight_id=freight_id, file_url=file_url, tipo=tipo, descricao=descricao, tenant_id=self._tenant_id)
        self._session.add(att)
        await self._session.flush()
        return att

    async def count_by_status(
        self,
        *,
        client_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
        period_from: date | None = None,
        period_to: date | None = None,
    ) -> dict[str, int]:
        query = select(Freight.status, func.count(Freight.id)).where(
            Freight.deleted_at.is_(None), Freight.tenant_id == self._tenant_id
        )
        query = self._apply_scope(
            query,
            client_id=client_id,
            driver_id=driver_id,
            truck_id=truck_id,
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
            period_from=period_from,
            period_to=period_to,
        )
        result = await self._session.execute(query.group_by(Freight.status))
        return {row[0].value: row[1] for row in result.all()}

    async def has_active_freight_for_truck(
        self,
        truck_id: uuid.UUID,
        exclude_freight_id: uuid.UUID | None = None,
    ) -> bool:
        """True if truck has a non-deleted freight in coleta/transporte (em viagem)."""
        query = self._base_query().where(
            Freight.truck_id == truck_id,
            Freight.status.in_((FreightStatus.EM_COLETA, FreightStatus.EM_TRANSPORTE)),
        )
        if exclude_freight_id:
            query = query.where(Freight.id != exclude_freight_id)
        return await self._count(query) > 0

    async def revenue_sum(self, status: FreightStatus | None = None) -> float:
        query = select(func.sum(Freight.valor_frete)).where(
            Freight.deleted_at.is_(None), Freight.tenant_id == self._tenant_id
        )
        if status:
            query = query.where(Freight.status == status)
        result = await self._session.execute(query)
        return float(result.scalar_one() or 0.0)
