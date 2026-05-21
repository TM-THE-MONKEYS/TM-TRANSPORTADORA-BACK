"""Pagination dependency."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query

from app.shared.pagination import PageParams


def get_page_params(
    page: int = Query(default=1, ge=1, description="Página (1-indexed)"),
    size: int = Query(default=20, ge=1, le=100, description="Itens por página"),
) -> PageParams:
    return PageParams(page=page, size=size)


PaginationDep = Annotated[PageParams, Depends(get_page_params)]
