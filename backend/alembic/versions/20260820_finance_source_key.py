"""Add source_key column for finance entry idempotency.

Revision ID: 20260820_finance_source_key
Revises: 20260730_finance_source_unique
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_finance_source_key"
down_revision: Union[str, Sequence[str], None] = "20260730_finance_source_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tm_finance_entries",
        sa.Column("source_key", sa.String(length=120), nullable=True),
    )
    op.create_index(
        "ix_tm_finance_entries_source_key_col",
        "tm_finance_entries",
        ["source_key"],
        unique=False,
    )

    # Backfill a partir do padrão legado em observacoes.
    op.execute(
        """
        UPDATE tm_finance_entries
        SET source_key = observacoes
        WHERE deleted_at IS NULL
          AND observacoes IS NOT NULL
          AND (
            observacoes LIKE 'freight_revenue:%'
            OR observacoes LIKE 'fuel_refill:%'
            OR observacoes LIKE 'toll_charge:%'
            OR observacoes LIKE 'freight_cost:%'
            OR observacoes LIKE 'commission:%'
            OR observacoes LIKE 'fixed_expense:%'
          )
        """
    )

    # Novo índice único em source_key (substitui o de observacoes).
    op.execute("DROP INDEX IF EXISTS ix_tm_finance_entries_source_key")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_tm_finance_entries_source_key_uid
        ON tm_finance_entries (tenant_id, source_key)
        WHERE deleted_at IS NULL
          AND source_key IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tm_finance_entries_source_key_uid")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_tm_finance_entries_source_key
        ON tm_finance_entries (tenant_id, observacoes)
        WHERE deleted_at IS NULL
          AND observacoes IS NOT NULL
          AND (
            observacoes LIKE 'freight_revenue:%'
            OR observacoes LIKE 'fuel_refill:%'
            OR observacoes LIKE 'toll_charge:%'
            OR observacoes LIKE 'freight_cost:%'
            OR observacoes LIKE 'commission:%'
            OR observacoes LIKE 'fixed_expense:%'
          )
        """
    )
    op.drop_index("ix_tm_finance_entries_source_key_col", table_name="tm_finance_entries")
    op.drop_column("tm_finance_entries", "source_key")
