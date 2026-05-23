"""Sincroniza receitas e despesas de fretes com tm_finance_entries."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.models import FinanceEntry
from app.modules.finance.repository import FinanceRepository
from app.modules.freights.models import Freight, FreightCost
from app.modules.fuel.models import FuelRefill
from app.modules.notifications.service import freight_code
from app.shared.enums import FinanceEntryStatus, FinanceEntryType

SOURCE_REVENUE = "freight_revenue:"
SOURCE_FUEL = "fuel_refill:"
SOURCE_COST = "freight_cost:"


async def _find_by_source(session: AsyncSession, source_key: str) -> FinanceEntry | None:
    result = await session.execute(
        select(FinanceEntry).where(
            FinanceEntry.deleted_at.is_(None),
            FinanceEntry.observacoes == source_key,
        )
    )
    return result.scalar_one_or_none()


async def ensure_freight_revenue(session: AsyncSession, freight: Freight) -> FinanceEntry | None:
    """Receita pendente vinculada ao valor do frete."""
    if float(freight.valor_frete or 0) <= 0:
        return None

    source_key = f"{SOURCE_REVENUE}{freight.id}"
    existing = await _find_by_source(session, source_key)
    code = freight_code(freight.id)
    vencimento: date | None = None
    if freight.data_entrega_prevista:
        dt = freight.data_entrega_prevista
        vencimento = dt.date() if isinstance(dt, datetime) else dt

    if existing:
        existing.valor = float(freight.valor_frete)
        existing.descricao = f"Receita frete {code}"
        existing.freight_id = freight.id
        if vencimento:
            existing.data_vencimento = vencimento
        return existing

    entry = FinanceEntry(
        tipo=FinanceEntryType.RECEITA,
        categoria="Frete",
        descricao=f"Receita frete {code}",
        valor=float(freight.valor_frete),
        freight_id=freight.id,
        data_vencimento=vencimento,
        status=FinanceEntryStatus.PENDENTE,
        observacoes=source_key,
    )
    return await FinanceRepository(session).create(entry)


async def create_fuel_expense(
    session: AsyncSession,
    refill: FuelRefill,
    description: str,
) -> FinanceEntry:
    """Despesa de combustível vinculada ao abastecimento."""
    source_key = f"{SOURCE_FUEL}{refill.id}"
    existing = await _find_by_source(session, source_key)
    if existing:
        existing.valor = float(refill.valor_total)
        existing.descricao = description
        existing.freight_id = refill.freight_id
        return existing

    paid_at = refill.data_abastecimento
    payment_date: date | None = None
    if paid_at:
        payment_date = paid_at.date() if isinstance(paid_at, datetime) else paid_at

    entry = FinanceEntry(
        tipo=FinanceEntryType.DESPESA,
        categoria="Combustível",
        descricao=description,
        valor=float(refill.valor_total),
        freight_id=refill.freight_id,
        status=FinanceEntryStatus.PAGO,
        data_pagamento=payment_date or date.today(),
        observacoes=source_key,
    )
    return await FinanceRepository(session).create(entry)


async def create_cost_expense(session: AsyncSession, cost: FreightCost) -> FinanceEntry | None:
    """Despesa genérica a partir de tm_freight_costs (exceto combustível já vinculado a abastecimento)."""
    if float(cost.valor or 0) <= 0:
        return None

    tipo_norm = (cost.tipo or "").upper()
    if "COMBUST" in tipo_norm:
        linked = await session.execute(
            select(FuelRefill.id).where(FuelRefill.freight_cost_id == cost.id).limit(1)
        )
        if linked.scalar_one_or_none():
            return None

    source_key = f"{SOURCE_COST}{cost.id}"
    existing = await _find_by_source(session, source_key)
    categoria = "Combustível" if "COMBUST" in tipo_norm else cost.tipo.title()
    descricao = cost.descricao or f"Custo {cost.tipo}"

    if existing:
        existing.valor = float(cost.valor)
        existing.descricao = descricao
        existing.categoria = categoria
        existing.freight_id = cost.freight_id
        return existing

    entry = FinanceEntry(
        tipo=FinanceEntryType.DESPESA,
        categoria=categoria,
        descricao=descricao,
        valor=float(cost.valor),
        freight_id=cost.freight_id,
        status=FinanceEntryStatus.PAGO,
        data_pagamento=date.today(),
        observacoes=source_key,
    )
    return await FinanceRepository(session).create(entry)


async def sync_all_from_freights(session: AsyncSession) -> dict[str, int]:
    """Backfill: receitas de fretes + despesas de abastecimentos e custos."""
    stats = {"receitas": 0, "despesas": 0}

    freights = (
        await session.execute(select(Freight).where(Freight.deleted_at.is_(None)))
    ).scalars().all()
    for freight in freights:
        if await ensure_freight_revenue(session, freight):
            stats["receitas"] += 1

    refills = (await session.execute(select(FuelRefill))).scalars().all()
    for refill in refills:
        desc = refill.posto or refill.observacoes or f"Abastecimento {refill.litros:.0f}L"
        await create_fuel_expense(session, refill, desc)
        stats["despesas"] += 1

    costs = (await session.execute(select(FreightCost))).scalars().all()
    for cost in costs:
        if await create_cost_expense(session, cost):
            stats["despesas"] += 1

    return stats
