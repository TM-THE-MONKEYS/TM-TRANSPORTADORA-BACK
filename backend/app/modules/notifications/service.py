"""Notification service."""
from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.freights.models import Freight
from app.modules.freights.repository import FreightRepository
from app.modules.notifications.models import FreightNotification
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.schemas import (
    MarkAllReadResponse,
    MarkReadResponse,
    NotificationItemRead,
    NotificationListResponse,
    UnreadCountResponse,
)
from app.modules.fuel.models import FuelRefill
from app.modules.tolls.models import TollCharge
from app.modules.tracking.models import TrackingUpdate
from app.modules.users.models import User
from app.shared.enums import (
    TRACKING_STATUS_LABELS,
    FreightStatus,
    NotificationType,
    TrackingStatus,
    UserRole,
)
from app.shared.exceptions.custom import ForbiddenException, NotFoundException

log = structlog.get_logger(__name__)

_NOTIFY_ROLES = frozenset({UserRole.ADMIN, UserRole.OPERADOR, UserRole.FINANCEIRO})


def freight_code(freight_id: uuid.UUID) -> str:
    return f"OF-{str(freight_id)[:8].upper()}"


def build_occurrence_message(
    status: TrackingStatus,
    descricao: str | None,
    cidade: str | None,
    estado: str | None,
) -> str:
    label = TRACKING_STATUS_LABELS.get(status, status.value)
    parts = [label]
    if cidade:
        loc = cidade.upper()
        if estado:
            loc += f"/{estado.upper()}"
        parts.append(f"— {loc}")
    if descricao and descricao.strip():
        parts.append(f"— {descricao.strip().upper()}")
    return " ".join(parts)


class NotificationService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = NotificationRepository(session, tenant_id)
        self._freight_repo = FreightRepository(session, tenant_id)

    def _check_read_access(self, user: User) -> None:
        if user.role not in _NOTIFY_ROLES:
            raise ForbiddenException("Acesso negado ao centro de notificações")

    async def create_for_tracking_update(
        self,
        tracking: TrackingUpdate,
        author: User,
    ) -> FreightNotification:
        code = freight_code(tracking.freight_id)
        titulo = f"NOVA OCORRÊNCIA NO FRETE {code}"
        mensagem = build_occurrence_message(
            tracking.status,
            tracking.descricao,
            tracking.cidade,
            tracking.estado,
        )
        notification = FreightNotification(
            freight_id=tracking.freight_id,
            tracking_update_id=tracking.id,
            tipo=NotificationType.TRACKING_OCCURRENCE,
            titulo=titulo,
            mensagem=mensagem,
            autor_user_id=author.id,
            autor_nome=author.nome.upper(),
            freight_code=code,
            tenant_id=self._tenant_id,
        )
        created = await self._repo.create(notification)
        log.info(
            "tracking_notification_created",
            notification_id=str(created.id),
            freight_id=str(tracking.freight_id),
            author_id=str(author.id),
        )
        return created

    async def create_for_fuel_refill(
        self,
        refill: FuelRefill,
        author: User,
    ) -> FreightNotification:
        code = freight_code(refill.freight_id)
        loc_parts: list[str] = []
        if refill.posto:
            loc_parts.append(refill.posto.upper())
        if refill.cidade:
            loc = refill.cidade.upper()
            if refill.estado:
                loc += f"/{refill.estado.upper()}"
            loc_parts.append(loc)
        loc = f" — {' / '.join(loc_parts)}" if loc_parts else ""
        mensagem = (
            f"ABASTECIMENTO {refill.litros:.2f}L — R$ {refill.valor_total:.2f}{loc}"
        )
        if refill.observacoes and refill.observacoes.strip():
            mensagem += f" — {refill.observacoes.strip().upper()}"

        notification = FreightNotification(
            freight_id=refill.freight_id,
            fuel_refill_id=refill.id,
            tracking_update_id=None,
            tipo=NotificationType.FUEL_REFILL,
            titulo=f"ABASTECIMENTO NO FRETE {code}",
            mensagem=mensagem,
            autor_user_id=author.id,
            autor_nome=author.nome.upper(),
            freight_code=code,
            tenant_id=self._tenant_id,
        )
        created = await self._repo.create(notification)
        log.info(
            "fuel_notification_created",
            notification_id=str(created.id),
            freight_id=str(refill.freight_id),
            author_id=str(author.id),
        )
        return created

    async def create_for_toll_charge(
        self,
        charge: TollCharge,
        author: User,
    ) -> FreightNotification:
        code = freight_code(charge.freight_id)
        loc_parts: list[str] = []
        if charge.praca:
            loc_parts.append(charge.praca.upper())
        if charge.rodovia:
            loc_parts.append(charge.rodovia.upper())
        if charge.cidade:
            loc = charge.cidade.upper()
            if charge.estado:
                loc += f"/{charge.estado.upper()}"
            loc_parts.append(loc)
        loc = f" — {' / '.join(loc_parts)}" if loc_parts else ""
        mensagem = (
            f"PEDÁGIO {charge.quantidade}x — R$ {charge.valor:.2f}{loc}"
        )
        if charge.observacoes and charge.observacoes.strip():
            mensagem += f" — {charge.observacoes.strip().upper()}"

        notification = FreightNotification(
            freight_id=charge.freight_id,
            toll_charge_id=charge.id,
            tracking_update_id=None,
            fuel_refill_id=None,
            tipo=NotificationType.TOLL_CHARGE,
            titulo=f"PEDÁGIO NO FRETE {code}",
            mensagem=mensagem,
            autor_user_id=author.id,
            autor_nome=author.nome.upper(),
            freight_code=code,
            tenant_id=self._tenant_id,
        )
        created = await self._repo.create(notification)
        log.info(
            "toll_notification_created",
            notification_id=str(created.id),
            freight_id=str(charge.freight_id),
            author_id=str(author.id),
        )
        return created

    async def list_notifications(
        self,
        user: User,
        *,
        unread_only: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> NotificationListResponse:
        self._check_read_access(user)
        offset = (page - 1) * size
        items, total, unread_count = await self._repo.list_for_user(
            user.id,
            unread_only=unread_only,
            limit=size,
            offset=offset,
        )
        enriched = await self._enrich_notifications(items)
        return NotificationListResponse(
            items=[
                self._to_item_read(n, is_read, ctx) for (n, is_read), ctx in zip(items, enriched)
            ],
            total=total,
            unread_count=unread_count,
        )

    async def get_unread_count(self, user: User) -> UnreadCountResponse:
        self._check_read_access(user)
        count = await self._repo.count_unread(user.id)
        return UnreadCountResponse(unread_count=count)

    async def mark_read(
        self, notification_id: uuid.UUID, user: User
    ) -> MarkReadResponse:
        self._check_read_access(user)
        notification = await self._repo.get_by_id(notification_id)
        if not notification:
            raise NotFoundException("Notificação não encontrada")
        await self._repo.mark_read(notification_id, user.id)
        await self._session.commit()
        return MarkReadResponse()

    async def mark_all_read(self, user: User) -> MarkAllReadResponse:
        self._check_read_access(user)
        count = await self._repo.mark_all_read(user.id)
        await self._session.commit()
        return MarkAllReadResponse(
            message="Todas as notificações foram marcadas como lidas",
            marked_count=count,
        )

    async def _enrich_notifications(
        self,
        items: list[tuple[FreightNotification, bool]],
    ) -> list[dict[str, object]]:
        if not items:
            return []
        tracking_ids = [n.tracking_update_id for n, _ in items if n.tracking_update_id]
        freight_ids = list({n.freight_id for n, _ in items})

        trackings: dict[uuid.UUID, TrackingUpdate] = {}
        if tracking_ids:
            tracking_result = await self._session.execute(
                select(TrackingUpdate).where(TrackingUpdate.id.in_(tracking_ids))
            )
            trackings = {t.id: t for t in tracking_result.scalars().all()}

        freight_result = await self._session.execute(
            select(Freight.id, Freight.status).where(Freight.id.in_(freight_ids))
        )
        freight_statuses = {row[0]: row[1] for row in freight_result.all()}

        contexts: list[dict[str, object]] = []
        for notification, _ in items:
            t = (
                trackings.get(notification.tracking_update_id)
                if notification.tracking_update_id
                else None
            )
            fs = freight_statuses.get(notification.freight_id)
            contexts.append(
                {
                    "tracking_status": t.status if t else None,
                    "cidade": t.cidade if t else None,
                    "estado": t.estado if t else None,
                    "freight_status": fs.value if fs else None,
                }
            )
        return contexts

    def _to_item_read(
        self,
        notification: FreightNotification,
        is_read: bool,
        ctx: dict[str, object],
    ) -> NotificationItemRead:
        return NotificationItemRead(
            id=notification.id,
            freight_id=notification.freight_id,
            tracking_update_id=notification.tracking_update_id,
            fuel_refill_id=notification.fuel_refill_id,
            toll_charge_id=notification.toll_charge_id,
            tipo=notification.tipo,
            titulo=notification.titulo,
            mensagem=notification.mensagem,
            autor_user_id=notification.autor_user_id,
            autor_nome=notification.autor_nome,
            freight_code=notification.freight_code,
            is_read=is_read,
            read_at=None,
            created_at=notification.created_at,
            freight_status=ctx.get("freight_status"),  # type: ignore[arg-type]
            tracking_status=ctx.get("tracking_status"),  # type: ignore[arg-type]
            cidade=ctx.get("cidade"),  # type: ignore[arg-type]
            estado=ctx.get("estado"),  # type: ignore[arg-type]
        )
