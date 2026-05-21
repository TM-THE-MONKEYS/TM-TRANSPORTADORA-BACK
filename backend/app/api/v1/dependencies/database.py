"""Database session dependency — re-exports from auth to share the same get_db."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]
