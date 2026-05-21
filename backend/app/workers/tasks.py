"""Celery tasks for background processing."""
from __future__ import annotations

import asyncio
from datetime import date

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


def _run_async(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.tasks.check_maintenance_alerts", bind=True, max_retries=3)
def check_maintenance_alerts(self) -> dict[str, int]:  # type: ignore[no-untyped-def]
    """Check and log upcoming maintenance alerts."""
    async def _run() -> dict[str, int]:
        from app.core.database.session import AsyncSessionLocal
        from app.modules.maintenance.repository import MaintenanceRepository

        async with AsyncSessionLocal() as session:
            repo = MaintenanceRepository(session)
            alerts = await repo.get_upcoming_alerts(days_ahead=7)
            log.info("maintenance_alerts_checked", count=len(alerts))
            return {"alerts_count": len(alerts)}

    try:
        return _run_async(_run())
    except Exception as exc:
        log.exception("check_maintenance_alerts_failed", exc=str(exc))
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="app.workers.tasks.mark_overdue_payments", bind=True, max_retries=3)
def mark_overdue_payments(self) -> dict[str, int]:  # type: ignore[no-untyped-def]
    """Mark finance entries as overdue if past due date."""
    async def _run() -> dict[str, int]:
        from sqlalchemy import update

        from app.core.database.session import AsyncSessionLocal
        from app.modules.finance.models import FinanceEntry
        from app.shared.enums import FinanceEntryStatus

        today = date.today()
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(FinanceEntry)
                .where(
                    FinanceEntry.status == FinanceEntryStatus.PENDENTE,
                    FinanceEntry.data_vencimento < today,
                    FinanceEntry.deleted_at.is_(None),
                )
                .values(status=FinanceEntryStatus.VENCIDO)
            )
            await session.commit()
            count = result.rowcount or 0
            log.info("overdue_payments_marked", count=count)
            return {"marked_count": count}

    try:
        return _run_async(_run())
    except Exception as exc:
        log.exception("mark_overdue_payments_failed", exc=str(exc))
        raise self.retry(exc=exc, countdown=3600)


@celery_app.task(name="app.workers.tasks.cleanup_expired_tokens", bind=True, max_retries=3)
def cleanup_expired_tokens(self) -> dict[str, int]:  # type: ignore[no-untyped-def]
    """Remove expired refresh tokens from database."""
    async def _run() -> dict[str, int]:
        from app.core.database.session import AsyncSessionLocal
        from app.modules.auth.repository import RefreshTokenRepository

        async with AsyncSessionLocal() as session:
            repo = RefreshTokenRepository(session)
            count = await repo.delete_expired()
            await session.commit()
            log.info("expired_tokens_cleaned", count=count)
            return {"deleted_count": count}

    try:
        return _run_async(_run())
    except Exception as exc:
        log.exception("cleanup_expired_tokens_failed", exc=str(exc))
        raise self.retry(exc=exc, countdown=300)
