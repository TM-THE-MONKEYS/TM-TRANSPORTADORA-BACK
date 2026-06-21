"""add commission_pct to drivers

Revision ID: 20260619_driver_commission_pct
Revises: 20260617_driver_fk_set_null
Create Date: 2026-06-19

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260619_driver_commission_pct"
down_revision: Union[str, Sequence[str], None] = "20260617_driver_fk_set_null"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tm_drivers",
        sa.Column("commission_pct", sa.Numeric(5, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tm_drivers", "commission_pct")
