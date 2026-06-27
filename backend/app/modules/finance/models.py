"""Finance model."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, SoftDeleteMixin, TenantMixin
from app.shared.enums import FinanceEntryStatus, FinanceEntryType, FixedExpenseFrequency


class FinanceEntry(TenantMixin, SoftDeleteMixin, BaseModel):
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


class FixedExpense(TenantMixin, SoftDeleteMixin, BaseModel):
    __tablename__ = "tm_fixed_expenses"

    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    categoria: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    frequencia: Mapped[FixedExpenseFrequency] = mapped_column(
        Enum(
            FixedExpenseFrequency,
            name="fixedexpensefrequency",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=FixedExpenseFrequency.MENSAL,
    )
    dia_vencimento: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_parcelas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parcelas_lancadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
