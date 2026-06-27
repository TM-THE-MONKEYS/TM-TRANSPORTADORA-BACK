"""Celery tasks for background processing."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

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
    """Check and log upcoming maintenance alerts across all tenants."""
    async def _run() -> dict[str, int]:
        from datetime import timedelta

        from sqlalchemy import func, select

        from app.core.database.session import AsyncSessionLocal
        from app.modules.maintenance.models import Maintenance
        from app.shared.enums import MaintenanceStatus

        cutoff = datetime.now(timezone.utc) + timedelta(days=7)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count(Maintenance.id)).where(
                    Maintenance.deleted_at.is_(None),
                    Maintenance.status == MaintenanceStatus.AGENDADA,
                    Maintenance.data_prevista <= cutoff,
                )
            )
            count = result.scalar_one()
            log.info("maintenance_alerts_checked", count=count)
            return {"alerts_count": count}

    try:
        return _run_async(_run())
    except Exception as exc:
        log.exception("check_maintenance_alerts_failed", exc=str(exc))
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="app.workers.tasks.mark_overdue_payments", bind=True, max_retries=3)
def mark_overdue_payments(self) -> dict[str, int]:  # type: ignore[no-untyped-def]
    """Mark finance entries as overdue if past due date (across all tenants)."""
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


@celery_app.task(name="app.workers.tasks.deactivate_expired_fixed_expenses", bind=True, max_retries=3)
def deactivate_expired_fixed_expenses(self) -> dict[str, int]:  # type: ignore[no-untyped-def]
    """Desativa gastos fixos expirados por data ou parcelas (todos os tenants)."""
    async def _run() -> dict[str, int]:
        from sqlalchemy import select

        from app.core.database.session import AsyncSessionLocal
        from app.modules.finance.fixed_expense_utils import refresh_expiry
        from app.modules.finance.models import FixedExpense

        deactivated = 0
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(FixedExpense).where(
                    FixedExpense.deleted_at.is_(None),
                    FixedExpense.ativo.is_(True),
                    FixedExpense.total_parcelas.isnot(None),
                )
            )
            for expense in result.scalars().all():
                if refresh_expiry(expense):
                    deactivated += 1
            await session.commit()
        log.info("fixed_expenses_deactivated", count=deactivated)
        return {"deactivated_count": deactivated}

    try:
        return _run_async(_run())
    except Exception as exc:
        log.exception("deactivate_expired_fixed_expenses_failed", exc=str(exc))
        raise self.retry(exc=exc, countdown=3600)


@celery_app.task(name="app.workers.tasks.cleanup_expired_tokens", bind=True, max_retries=3)
def cleanup_expired_tokens(self) -> dict[str, int]:  # type: ignore[no-untyped-def]
    """Remove expired refresh tokens from database (across all tenants)."""
    async def _run() -> dict[str, int]:
        from sqlalchemy import delete

        from app.core.database.session import AsyncSessionLocal
        from app.modules.auth.models import RefreshToken

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                delete(RefreshToken).where(
                    RefreshToken.expires_at < datetime.now(timezone.utc)
                )
            )
            await session.commit()
            count = result.rowcount or 0
            log.info("expired_tokens_cleaned", count=count)
            return {"deleted_count": count}

    try:
        return _run_async(_run())
    except Exception as exc:
        log.exception("cleanup_expired_tokens_failed", exc=str(exc))
        raise self.retry(exc=exc, countdown=300)
