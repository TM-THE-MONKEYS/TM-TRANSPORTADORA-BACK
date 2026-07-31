"""Unique index on finance entry source keys (observacoes prefixes).

Revision ID: 20260730_finance_source_unique
Revises: 20260623_backend_features
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260730_finance_source_unique"
down_revision: Union[str, Sequence[str], None] = "20260623_backend_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tm_finance_entries_source_key")
