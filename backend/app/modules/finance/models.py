"""Finance model."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, SoftDeleteMixin
from app.shared.enums import FinanceEntryStatus, FinanceEntryType


class FinanceEntry(SoftDeleteMixin, BaseModel):
    __tablename__ = "tm_finance_entries"

    tipo: Mapped[FinanceEntryType] = mapped_column(
        Enum(FinanceEntryType, name="financeentrytype", create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True
    )
    categoria: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    freight_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tm_freights.id", ondelete="SET NULL"), nullable=True, index=True
    )
    data_vencimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_pagamento: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[FinanceEntryStatus] = mapped_column(
        Enum(FinanceEntryStatus, name="financeentrystatus", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=FinanceEntryStatus.PENDENTE,
        index=True,
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
