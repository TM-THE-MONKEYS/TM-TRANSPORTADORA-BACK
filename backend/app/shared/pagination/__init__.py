"""Generic pagination schemas and utilities."""
from __future__ import annotations

import math
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size


class PagedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        params: PageParams,
    ) -> "PagedResponse[T]":
        pages = math.ceil(total / params.size) if total > 0 else 1
        return cls(
            items=items,
            total=total,
            page=params.page,
            size=params.size,
            pages=pages,
            has_next=params.page < pages,
            has_prev=params.page > 1,
        )
