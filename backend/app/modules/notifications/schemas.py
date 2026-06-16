"""Notification schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import NotificationType, TrackingStatus


class NotificationItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    freight_id: uuid.UUID
    tracking_update_id: uuid.UUID | None = None
    fuel_refill_id: uuid.UUID | None = None
    toll_charge_id: uuid.UUID | None = None
    tipo: NotificationType
    titulo: str
    mensagem: str
    autor_user_id: uuid.UUID | None
    autor_nome: str
    freight_code: str
    is_read: bool = False
    read_at: datetime | None = None
    created_at: datetime

    # Contexto para navegação no front
    freight_status: str | None = None
    tracking_status: TrackingStatus | None = None
    cidade: str | None = None
    estado: str | None = None


class NotificationListResponse(BaseModel):
    items: list[NotificationItemRead]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkReadResponse(BaseModel):
    message: str = "Notificação marcada como lida"


class MarkAllReadResponse(BaseModel):
    message: str
    marked_count: int
