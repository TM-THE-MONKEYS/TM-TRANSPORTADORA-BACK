"""Tracking routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.tracking.schemas import (
    TrackingFreightDetailResponse,
    TrackingTimelineResponse,
    TrackingUpdateCreate,
    TrackingUpdateCreatedResponse,
)
from app.modules.tracking.service import TrackingService
from app.modules.users.models import User

router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.post(
    "",
    response_model=TrackingUpdateCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_tracking_update(
    payload: TrackingUpdateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TrackingUpdateCreatedResponse:
    service = TrackingService(db, current_user.tenant_id)
    return await service.add_update(payload, current_user)


@router.get("/{freight_id}/detail", response_model=TrackingFreightDetailResponse)
async def get_freight_tracking_detail(
    freight_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TrackingFreightDetailResponse:
    """Tela de rastreamento: frete + linha do tempo de ocorrências."""
    service = TrackingService(db, current_user.tenant_id)
    return await service.get_freight_detail(freight_id, current_user)


@router.get("/{freight_id}/timeline", response_model=TrackingTimelineResponse)
async def get_freight_timeline(
    freight_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TrackingTimelineResponse:
    service = TrackingService(db, current_user.tenant_id)
    return await service.get_timeline(freight_id, current_user)
