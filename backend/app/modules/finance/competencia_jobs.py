"""In-process fallback store for competência report jobs (tests / broker down)."""
from __future__ import annotations

import uuid
from typing import Any

_LOCAL_JOBS: dict[str, dict[str, Any]] = {}


def store_local_job(payload: dict[str, Any], *, job_id: str | None = None) -> str:
    jid = job_id or str(uuid.uuid4())
    _LOCAL_JOBS[jid] = {"status": "success", "result": payload}
    return jid


def get_local_job(job_id: str) -> dict[str, Any] | None:
    return _LOCAL_JOBS.get(job_id)


def clear_local_jobs() -> None:
    _LOCAL_JOBS.clear()
