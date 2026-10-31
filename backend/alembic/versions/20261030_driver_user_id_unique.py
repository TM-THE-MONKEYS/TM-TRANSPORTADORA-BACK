"""Unique partial index on tm_drivers.user_id (non-null).

Revision ID: 20261030_driver_user_id_unique
Revises: 20260820_finance_source_key
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20261030_driver_user_id_unique"
down_revision: Union[str, Sequence[str], None] = "20260820_finance_source_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop non-unique index created by earlier schema (name may vary by dialect).
    op.execute("DROP INDEX IF EXISTS ix_tm_drivers_user_id")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_tm_drivers_user_id_not_null
        ON tm_drivers (user_id)
        WHERE user_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_tm_drivers_user_id_not_null")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_tm_drivers_user_id
        ON tm_drivers (user_id)
        """
    )
