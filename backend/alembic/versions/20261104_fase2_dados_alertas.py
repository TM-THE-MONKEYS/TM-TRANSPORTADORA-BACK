"""Fase 2: tanque_cheio, campos de negócio e suporte a alertas.

Revision ID: 20261104_fase2_dados_alertas
Revises: 20261104_history_integrity
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261104_fase2_dados_alertas"
down_revision: str | Sequence[str] | None = "20261104_history_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tm_fuel_refills",
        sa.Column(
            "tanque_cheio",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "tm_finance_entries",
        sa.Column("forma_pagamento", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "tm_clients",
        sa.Column("prazo_pagamento_dias", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tm_freights",
        sa.Column("motivo_cancelamento", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "tm_freights",
        sa.Column("motivo_cancelamento_detalhe", sa.Text(), nullable=True),
    )
    op.add_column(
        "tm_freights",
        sa.Column("motivo_atraso", sa.String(length=40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tm_freights", "motivo_atraso")
    op.drop_column("tm_freights", "motivo_cancelamento_detalhe")
    op.drop_column("tm_freights", "motivo_cancelamento")
    op.drop_column("tm_clients", "prazo_pagamento_dias")
    op.drop_column("tm_finance_entries", "forma_pagamento")
    op.drop_column("tm_fuel_refills", "tanque_cheio")
