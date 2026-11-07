"""Short-TTL Redis cache for freights summary (+ dashboard KPI invalidation)."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from app.shared.enums import FreightStatus

log = structlog.get_logger(__name__)

_SUMMARY_TTL_SECONDS = 45
_SUMMARY_PREFIX = "freight:summary"
_DASH_KPI_PREFIX = "dash:kpis"


def _filters_hash(
    *,
    status: FreightStatus | None,
    driver_id: uuid.UUID | None,
    truck_id: uuid.UUID | None,
    competencia_mes: int | None,
    competencia_ano: int | None,
) -> str:
    payload = {
        "status": status.value if status else None,
        "driver_id": str(driver_id) if driver_id else None,
        "truck_id": str(truck_id) if truck_id else None,
        "competencia_mes": competencia_mes,
        "competencia_ano": competencia_ano,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def freight_summary_cache_key(
    tenant_id: uuid.UUID,
    *,
    status: FreightStatus | None = None,
    driver_id: uuid.UUID | None = None,
    truck_id: uuid.UUID | None = None,
    competencia_mes: int | None = None,
    competencia_ano: int | None = None,
) -> str:
    return (
        f"{_SUMMARY_PREFIX}:{tenant_id}:"
        f"{_filters_hash(status=status, driver_id=driver_id, truck_id=truck_id, competencia_mes=competencia_mes, competencia_ano=competencia_ano)}"
    )


async def get_cached_freight_summary(
    tenant_id: uuid.UUID,
    *,
    status: FreightStatus | None,
    driver_id: uuid.UUID | None,
    truck_id: uuid.UUID | None,
    competencia_mes: int | None,
    competencia_ano: int | None,
    compute: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    cache_key = freight_summary_cache_key(
        tenant_id,
        status=status,
        driver_id=driver_id,
        truck_id=truck_id,
        competencia_mes=competencia_mes,
        competencia_ano=competencia_ano,
    )
    try:
        from app.core.database.redis import get_redis

        redis = get_redis()
        cached = await redis.get(cache_key)
        if cached:
            log.debug("freight_summary_cache_hit", cache_key=cache_key)
            return json.loads(cached)
        log.debug("freight_summary_cache_miss", cache_key=cache_key)
    except Exception:
        log.debug("freight_summary_cache_unavailable", cache_key=cache_key, exc_info=True)

    data = await compute()

    try:
        from app.core.database.redis import get_redis

        redis = get_redis()
        await redis.setex(cache_key, _SUMMARY_TTL_SECONDS, json.dumps(data))
    except Exception:
        log.debug("freight_summary_cache_set_failed", cache_key=cache_key, exc_info=True)

    return data


async def invalidate_tenant_aggregates_cache(tenant_id: uuid.UUID) -> None:
    """Drop freight summary + dashboard KPI keys for a tenant after writes."""
    patterns = (
        f"{_SUMMARY_PREFIX}:{tenant_id}:*",
        f"{_DASH_KPI_PREFIX}:{tenant_id}:*",
    )
    try:
        from app.core.database.redis import get_redis

        redis = get_redis()
        deleted = 0
        for pattern in patterns:
            async for key in redis.scan_iter(match=pattern, count=100):
                await redis.delete(key)
                deleted += 1
        if deleted:
            log.info(
                "tenant_aggregates_cache_invalidated",
                tenant_id=str(tenant_id),
                keys_deleted=deleted,
            )
    except Exception:
        log.debug(
            "tenant_aggregates_cache_invalidate_failed",
            tenant_id=str(tenant_id),
            exc_info=True,
        )
