"""truck implements table

Revision ID: 20260621_truck_implements
Revises: 20260619_driver_commission_pct
Create Date: 2026-06-21

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260621_truck_implements"
down_revision: Union[str, Sequence[str], None] = "20260619_driver_commission_pct"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tm_truck_implements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("truck_id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("placa", sa.String(length=10), nullable=True),
        sa.Column("identificador", sa.String(length=50), nullable=True),
        sa.Column("marca", sa.String(length=100), nullable=True),
        sa.Column("modelo", sa.String(length=100), nullable=True),
        sa.Column("capacidade_kg", sa.Float(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tm_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["truck_id"], ["tm_trucks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tm_truck_implements_truck_id", "tm_truck_implements", ["truck_id"])
    op.create_index("ix_tm_truck_implements_placa", "tm_truck_implements", ["placa"])
    op.create_index("ix_tm_truck_implements_deleted_at", "tm_truck_implements", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_tm_truck_implements_deleted_at", table_name="tm_truck_implements")
    op.drop_index("ix_tm_truck_implements_placa", table_name="tm_truck_implements")
    op.drop_index("ix_tm_truck_implements_truck_id", table_name="tm_truck_implements")
    op.drop_table("tm_truck_implements")
