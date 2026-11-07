"""Composite indexes for freights list/competência filters.

Revision ID: 20261107_freight_composite_indexes
Revises: 20261030_driver_user_id_unique
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20261107_freight_composite_indexes"
down_revision: Union[str, Sequence[str], None] = "20261030_driver_user_id_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # List default order + tenant scope (deleted_at filtered in WHERE).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_tm_freights_tenant_created_at
        ON tm_freights (tenant_id, created_at DESC)
        """
    )
    # Competência path: data_entrega_real is primary fallback.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_tm_freights_tenant_data_entrega_real
        ON tm_freights (tenant_id, data_entrega_real)
        """
    )
    # Motorista / frota scoped lists: tenant + driver + status.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_tm_freights_tenant_driver_status
        ON tm_freights (tenant_id, driver_id, status)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tm_freights_tenant_driver_status")
    op.execute("DROP INDEX IF EXISTS ix_tm_freights_tenant_data_entrega_real")
    op.execute("DROP INDEX IF EXISTS ix_tm_freights_tenant_created_at")
