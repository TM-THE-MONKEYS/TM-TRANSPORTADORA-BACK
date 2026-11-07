"""Shared httpx client defaults for outbound HTTP."""
from __future__ import annotations

from typing import Any

import httpx

# Conservative defaults for any future outbound calls (APIs, webhooks, etc.).
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)


def create_http_client(**kwargs: Any) -> httpx.AsyncClient:
    """Build an AsyncClient with timeout defaults (kwargs override)."""
    timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
    return httpx.AsyncClient(timeout=timeout, **kwargs)
