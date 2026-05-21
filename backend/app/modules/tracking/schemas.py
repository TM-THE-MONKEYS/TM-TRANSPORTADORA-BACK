"""Tracking schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import TrackingStatus


class TrackingUpdateCreate(BaseModel):
    freight_id: uuid.UUID
    status: TrackingStatus
    descricao: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    cidade: str | None = Field(default=None, max_length=100)
    estado: str | None = Field(default=None, max_length=2)
    evento_at: datetime | None = None


class TrackingUpdateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    freight_id: uuid.UUID
    status: TrackingStatus
    descricao: str | None
    latitude: float | None
    longitude: float | None
    cidade: str | None
    estado: str | None
    evento_at: datetime
    created_at: datetime


class TrackingTimelineResponse(BaseModel):
    freight_id: uuid.UUID
    updates: list[TrackingUpdateRead]
    current_status: TrackingStatus | None
