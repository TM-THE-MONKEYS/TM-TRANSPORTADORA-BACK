"""Tracking model."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel, TenantMixin
from app.shared.enums import TrackingStatus


class TrackingUpdate(TenantMixin, BaseModel):
    __tablename__ = "tm_tracking_updates"

    freight_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tm_freights.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[TrackingStatus] = mapped_column(
        Enum(TrackingStatus, name="trackingstatus", create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True)
    evento_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    freight: Mapped["Freight"] = relationship(back_populates="tracking_updates")  # type: ignore[name-defined]  # noqa: F821
