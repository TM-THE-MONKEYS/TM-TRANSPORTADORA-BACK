"""Tracking routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.tracking.schemas import (
    TrackingTimelineResponse,
    TrackingUpdateCreate,
    TrackingUpdateRead,
)
from app.modules.tracking.service import TrackingService
from app.modules.users.models import User

router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.post("", response_model=TrackingUpdateRead, status_code=status.HTTP_201_CREATED)
async def add_tracking_update(
    payload: TrackingUpdateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TrackingUpdateRead:
    service = TrackingService(db)
    return await service.add_update(payload, current_user)  # type: ignore[return-value]


@router.get("/{freight_id}/timeline", response_model=TrackingTimelineResponse)
async def get_freight_timeline(
    freight_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TrackingTimelineResponse:
    service = TrackingService(db)
    return await service.get_timeline(freight_id)
