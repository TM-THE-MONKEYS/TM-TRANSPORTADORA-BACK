"""User model."""
from __future__ import annotations

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel, SoftDeleteMixin, TenantMixin
from app.shared.enums import UserRole


class User(TenantMixin, SoftDeleteMixin, BaseModel):
    __tablename__ = "tm_users"

    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.OPERADOR,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )
