"""Auth models: refresh tokens."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel


class RefreshToken(BaseModel):
    __tablename__ = "tm_refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")  # type: ignore[name-defined]  # noqa: F821

    @property
    def is_valid(self) -> bool:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        # Handle naive datetimes (SQLite returns naive)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        revoked = self.revoked_at
        if revoked is not None and revoked.tzinfo is None:
            revoked = revoked.replace(tzinfo=timezone.utc)
        return revoked is None and expires > now
