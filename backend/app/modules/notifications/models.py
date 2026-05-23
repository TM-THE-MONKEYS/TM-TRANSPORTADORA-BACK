"""Freight occurrence notifications."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel
from app.shared.enums import NotificationType


class FreightNotification(BaseModel):
    """Notificação gerada quando motorista/operador registra ocorrência de rastreamento."""

    __tablename__ = "tm_freight_notifications"

    freight_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_freights.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tracking_update_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_tracking_updates.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    fuel_refill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_fuel_refills.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    tipo: Mapped[NotificationType] = mapped_column(
        Enum(
            NotificationType,
            name="notificationtype",
            native_enum=False,
            length=50,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=NotificationType.TRACKING_OCCURRENCE,
    )
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    autor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    autor_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    freight_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    reads: Mapped[list["NotificationRead"]] = relationship(
        back_populates="notification",
        cascade="all, delete-orphan",
        lazy="noload",
    )


class NotificationRead(BaseModel):
    """Controle de leitura por usuário (badge / centro de notificações)."""

    __tablename__ = "tm_notification_reads"
    __table_args__ = (
        UniqueConstraint("notification_id", "user_id", name="uq_notification_read_user"),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_freight_notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    notification: Mapped["FreightNotification"] = relationship(back_populates="reads")
