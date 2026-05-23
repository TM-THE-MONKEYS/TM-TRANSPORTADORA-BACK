"""Tracking schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.fuel.schemas import FuelRefillRead
from app.shared.enums import FreightStatus, TrackingStatus
from app.shared.utils.data_normalization import apply_field_rules


class TrackingUpdateCreate(BaseModel):
    freight_id: uuid.UUID
    status: TrackingStatus
    descricao: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    cidade: str | None = Field(default=None, max_length=100)
    estado: str | None = Field(default=None, max_length=2)
    evento_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: object) -> object:
        if isinstance(data, dict):
            apply_field_rules(
                data,
                {
                    "descricao": "upper",
                    "cidade": "upper",
                    "estado": "uf",
                },
            )
        return data


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
    status_label: str | None = None


class TrackingUpdateCreatedResponse(TrackingUpdateRead):
    """Resposta ao criar ocorrência — inclui notificação gerada."""

    notification_id: uuid.UUID | None = None


class TrackingTimelineResponse(BaseModel):
    freight_id: uuid.UUID
    updates: list[TrackingUpdateRead]
    current_status: TrackingStatus | None
    total_occurrences: int = 0


class TrackingFreightSummary(BaseModel):
    """Resumo do frete para tela de rastreamento."""

    id: uuid.UUID
    code: str
    status: FreightStatus
    customer_id: uuid.UUID
    customer_name: str | None = None
    driver_id: uuid.UUID | None = None
    driver_name: str | None = None
    truck_id: uuid.UUID | None = None
    truck_plate: str | None = None
    origin_city: str
    origin_state: str
    destination_city: str
    destination_state: str
    value_brl: float


class TrackingFreightDetailResponse(BaseModel):
    """Payload completo para a tela de rastreamento de carga."""

    freight: TrackingFreightSummary
    current_status: TrackingStatus | None
    latest_occurrence: TrackingUpdateRead | None
    timeline: list[TrackingUpdateRead]
    total_occurrences: int
    unread_notifications: int = 0
    fuel_refills: list[FuelRefillRead] = []
    fuel_total_litros: float = 0.0
    fuel_total_valor: float = 0.0
