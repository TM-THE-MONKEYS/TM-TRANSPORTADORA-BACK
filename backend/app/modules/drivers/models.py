"""Driver model."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, SoftDeleteMixin
from app.shared.enums import CNHCategory, DriverStatus


class Driver(SoftDeleteMixin, BaseModel):
    __tablename__ = "tm_drivers"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tm_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cpf: Mapped[str] = mapped_column(String(14), nullable=False, unique=True, index=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    cnh: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    cnh_category: Mapped[CNHCategory] = mapped_column(
        Enum(CNHCategory, name="cnhcategory", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    cnh_expiry: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[DriverStatus] = mapped_column(
        Enum(DriverStatus, name="driverstatus", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=DriverStatus.ATIVO,
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
