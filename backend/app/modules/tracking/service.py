"""Tracking service."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.drivers.models import Driver
from app.modules.freights.models import Freight
from app.modules.freights.repository import FreightRepository
from app.modules.fuel.repository import FuelRepository
from app.modules.fuel.service import FuelService
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService, freight_code
from app.modules.tracking.models import TrackingUpdate
from app.modules.tracking.repository import TrackingRepository
from app.modules.tracking.schemas import (
    TrackingFreightDetailResponse,
    TrackingFreightSummary,
    TrackingTimelineResponse,
    TrackingUpdateCreate,
    TrackingUpdateCreatedResponse,
    TrackingUpdateRead,
)
from app.modules.trucks.models import Truck
from app.modules.users.models import User
from app.shared.enums import TRACKING_STATUS_LABELS, UserRole
from app.shared.exceptions.custom import ForbiddenException, NotFoundException
from app.shared.security.resource_access import assert_freight_read_access

log = structlog.get_logger(__name__)


class TrackingService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = TrackingRepository(session, tenant_id)
        self._freight_repo = FreightRepository(session, tenant_id)
        self._notification_repo = NotificationRepository(session, tenant_id)
        self._fuel_repo = FuelRepository(session, tenant_id)

    def _check_write_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR, UserRole.MOTORISTA):
            raise ForbiddenException("Acesso negado")

    async def _check_freight_access(self, freight: Freight, user: User) -> None:
        await assert_freight_read_access(self._session, freight, user)

    def _to_update_read(self, update: TrackingUpdate) -> TrackingUpdateRead:
        return TrackingUpdateRead(
            id=update.id,
            freight_id=update.freight_id,
            status=update.status,
            descricao=update.descricao,
            latitude=update.latitude,
            longitude=update.longitude,
            cidade=update.cidade,
            estado=update.estado,
            evento_at=update.evento_at,
            created_at=update.created_at,
            status_label=TRACKING_STATUS_LABELS.get(update.status, update.status.value),
        )

    async def add_update(
        self, data: TrackingUpdateCreate, added_by: User
    ) -> TrackingUpdateCreatedResponse:
        self._check_write_access(added_by)
        freight = await self._freight_repo.get_by_id(data.freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        await self._check_freight_access(freight, added_by)

        tracking = TrackingUpdate(
            freight_id=data.freight_id,
            status=data.status,
            descricao=data.descricao,
            latitude=data.latitude,
            longitude=data.longitude,
            cidade=data.cidade,
            estado=data.estado,
            evento_at=data.evento_at or datetime.now(timezone.utc),
            tenant_id=self._tenant_id,
        )
        tracking = await self._repo.create(tracking)

        notification_service = NotificationService(self._session, self._tenant_id)
        notification = await notification_service.create_for_tracking_update(
            tracking, added_by
        )

        await self._session.commit()
        log.info(
            "tracking_update_added",
            freight_id=str(data.freight_id),
            status=data.status.value,
            notification_id=str(notification.id),
        )
        base = self._to_update_read(tracking)
        return TrackingUpdateCreatedResponse(
            **base.model_dump(),
            notification_id=notification.id,
        )

    async def get_timeline(
        self, freight_id: uuid.UUID, user: User
    ) -> TrackingTimelineResponse:
        freight = await self._freight_repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        await self._check_freight_access(freight, user)
        updates = await self._repo.get_by_freight(freight_id)
        reads = [self._to_update_read(u) for u in updates]
        latest = reads[-1] if reads else None
        return TrackingTimelineResponse(
            freight_id=freight_id,
            updates=reads,
            current_status=latest.status if latest else None,
            total_occurrences=len(reads),
        )

    async def get_freight_detail(
        self, freight_id: uuid.UUID, user: User
    ) -> TrackingFreightDetailResponse:
        freight = await self._freight_repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        await self._check_freight_access(freight, user)

        client_name: str | None = None
        if freight.client_id:
            client = await self._session.get(Client, freight.client_id)
            client_name = client.nome if client else None

        driver_name: str | None = None
        if freight.driver_id:
            driver = await self._session.get(Driver, freight.driver_id)
            driver_name = driver.nome if driver else None

        truck_plate: str | None = None
        if freight.truck_id:
            truck = await self._session.get(Truck, freight.truck_id)
            truck_plate = truck.placa if truck else None

        origem = freight.origem or {}
        destino = freight.destino or {}
        summary = TrackingFreightSummary(
            id=freight.id,
            code=freight_code(freight.id),
            status=freight.status,
            customer_id=freight.client_id,
            customer_name=client_name,
            driver_id=freight.driver_id,
            driver_name=driver_name,
            truck_id=freight.truck_id,
            truck_plate=truck_plate,
            origin_city=origem.get("cidade", ""),
            origin_state=origem.get("estado", ""),
            destination_city=destino.get("cidade", ""),
            destination_state=destino.get("estado", ""),
            value_brl=freight.valor_frete,
        )

        updates = await self._repo.get_by_freight(freight_id)
        timeline = [self._to_update_read(u) for u in updates]
        latest = timeline[-1] if timeline else None

        unread = 0
        if user.role in (UserRole.ADMIN, UserRole.OPERADOR, UserRole.FINANCEIRO):
            unread = await self._notification_repo.count_unread(user.id)

        fuel_items, _ = await self._fuel_repo.list_by_freight(
            freight_id, limit=50, offset=0
        )
        fuel_service = FuelService(self._session, self._tenant_id)
        fuel_reads = [await fuel_service._enrich_read(r) for r in fuel_items]
        total_litros, total_valor, _ = await self._fuel_repo.summarize_freight(freight_id)

        return TrackingFreightDetailResponse(
            freight=summary,
            current_status=latest.status if latest else None,
            latest_occurrence=latest,
            timeline=timeline,
            total_occurrences=len(timeline),
            unread_notifications=unread,
            fuel_refills=fuel_reads,
            fuel_total_litros=total_litros,
            fuel_total_valor=total_valor,
        )
