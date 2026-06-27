"""Celery application configuration."""
from __future__ import annotations

from celery import Celery

from app.core.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "tm_transportadora",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "check-maintenance-alerts": {
            "task": "app.workers.tasks.check_maintenance_alerts",
            "schedule": 3600.0,  # every hour
        },
        "mark-overdue-payments": {
            "task": "app.workers.tasks.mark_overdue_payments",
            "schedule": 86400.0,  # every day
        },
        "deactivate-expired-fixed-expenses": {
            "task": "app.workers.tasks.deactivate_expired_fixed_expenses",
            "schedule": 86400.0,  # every day
        },
        "cleanup-expired-tokens": {
            "task": "app.workers.tasks.cleanup_expired_tokens",
            "schedule": 3600.0,  # every hour
        },
    },
)
