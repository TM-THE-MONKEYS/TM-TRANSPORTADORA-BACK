"""Cálculo de consumo real (km/l) e custo por km por caminhão."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.freights.models import Freight
from app.modules.fuel.models import FuelRefill
from app.modules.tolls.models import TollCharge
from app.modules.trucks.models import Truck

# Desvio percentual em relação ao consumo cadastrado para destacar alerta.
_DEVIATION_THRESHOLD = 0.15


@dataclass(frozen=True)
class ConsumptionSegment:
    from_refill_id: uuid.UUID
    to_refill_id: uuid.UUID
    km_start: float
    km_end: float
    km_rodado: float
    litros: float
    km_l: float


@dataclass(frozen=True)
class TruckConsumptionReport:
    truck_id: uuid.UUID
    placa: str
    consumo_cadastrado_km_l: float | None
    consumo_real_km_l: float | None
    desvio_pct: float | None
    desvio_relevante: bool
    km_rodado_total: float
    custo_combustivel: float
    custo_pedagio: float
    custo_por_km: float | None
    segmentos: list[ConsumptionSegment]


def _segments_from_full_tanks(
    refills: list[FuelRefill],
) -> list[ConsumptionSegment]:
    """Pares consecutivos de tanque cheio com km válido e não decrescente."""
    full = [
        r
        for r in refills
        if r.tanque_cheio and r.km_atual is not None
    ]
    segments: list[ConsumptionSegment] = []
    for prev, curr in zip(full, full[1:], strict=False):
        km_start = float(prev.km_atual or 0)
        km_end = float(curr.km_atual or 0)
        if km_end <= km_start:
            continue
        litros = float(curr.litros)
        if litros <= 0:
            continue
        km_rodado = km_end - km_start
        segments.append(
            ConsumptionSegment(
                from_refill_id=prev.id,
                to_refill_id=curr.id,
                km_start=km_start,
                km_end=km_end,
                km_rodado=km_rodado,
                litros=litros,
                km_l=km_rodado / litros,
            )
        )
    return segments


async def build_truck_consumption(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    truck: Truck,
) -> TruckConsumptionReport:
    refill_rows = list(
        (
            await session.execute(
                select(FuelRefill)
                .where(
                    FuelRefill.deleted_at.is_(None),
                    FuelRefill.tenant_id == tenant_id,
                    FuelRefill.truck_id == truck.id,
                )
                .order_by(
                    FuelRefill.data_abastecimento.asc(),
                    FuelRefill.created_at.asc(),
                )
            )
        ).scalars().all()
    )
    segments = _segments_from_full_tanks(refill_rows)

    real_km_l: float | None = None
    km_rodado_total = 0.0
    if segments:
        total_km = sum(s.km_rodado for s in segments)
        total_litros = sum(s.litros for s in segments)
        km_rodado_total = total_km
        if total_litros > 0:
            real_km_l = total_km / total_litros

    cadastrado = truck.consumo_km_l
    desvio_pct: float | None = None
    desvio_relevante = False
    if real_km_l is not None and cadastrado and cadastrado > 0:
        desvio_pct = (real_km_l - float(cadastrado)) / float(cadastrado)
        desvio_relevante = abs(desvio_pct) >= _DEVIATION_THRESHOLD

    fuel_cost = float(
        (
            await session.execute(
                select(func.coalesce(func.sum(FuelRefill.valor_total), 0.0)).where(
                    FuelRefill.deleted_at.is_(None),
                    FuelRefill.tenant_id == tenant_id,
                    FuelRefill.truck_id == truck.id,
                )
            )
        ).scalar_one()
    )
    toll_cost = float(
        (
            await session.execute(
                select(func.coalesce(func.sum(TollCharge.valor), 0.0))
                .select_from(TollCharge)
                .join(Freight, Freight.id == TollCharge.freight_id)
                .where(
                    TollCharge.deleted_at.is_(None),
                    TollCharge.tenant_id == tenant_id,
                    Freight.deleted_at.is_(None),
                    Freight.truck_id == truck.id,
                )
            )
        ).scalar_one()
    )

    # Fallback de km: se não houver pares tanque cheio, usa span de km nos
    # abastecimentos com odômetro (ainda assim ignora decréscimo).
    if km_rodado_total <= 0:
        with_km = [r for r in refill_rows if r.km_atual is not None]
        if len(with_km) >= 2:
            first = float(with_km[0].km_atual or 0)
            last = float(with_km[-1].km_atual or 0)
            if last > first:
                km_rodado_total = last - first

    custo_total = fuel_cost + toll_cost
    custo_por_km = (
        custo_total / km_rodado_total if km_rodado_total > 0 else None
    )

    return TruckConsumptionReport(
        truck_id=truck.id,
        placa=truck.placa,
        consumo_cadastrado_km_l=float(cadastrado) if cadastrado else None,
        consumo_real_km_l=real_km_l,
        desvio_pct=desvio_pct,
        desvio_relevante=desvio_relevante,
        km_rodado_total=km_rodado_total,
        custo_combustivel=fuel_cost,
        custo_pedagio=toll_cost,
        custo_por_km=custo_por_km,
        segmentos=segments,
    )
