"""fuel refills and notification link

Revision ID: 20260523_020000
Revises: 20260523_010000
Create Date: 2026-05-23

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260523_020000"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tm_fuel_refills",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("freight_id", sa.UUID(), nullable=False),
        sa.Column("driver_id", sa.UUID(), nullable=False),
        sa.Column("truck_id", sa.UUID(), nullable=True),
        sa.Column("registrado_por_user_id", sa.UUID(), nullable=True),
        sa.Column("freight_cost_id", sa.UUID(), nullable=True),
        sa.Column("litros", sa.Float(), nullable=False),
        sa.Column("valor_total", sa.Float(), nullable=False),
        sa.Column("valor_litro", sa.Float(), nullable=True),
        sa.Column("km_atual", sa.Float(), nullable=True),
        sa.Column("posto", sa.String(length=150), nullable=True),
        sa.Column("cidade", sa.String(length=100), nullable=True),
        sa.Column("estado", sa.String(length=2), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("data_abastecimento", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["driver_id"], ["tm_drivers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["freight_cost_id"], ["tm_freight_costs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["freight_id"], ["tm_freights.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["registrado_por_user_id"], ["tm_users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["truck_id"], ["tm_trucks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("freight_cost_id"),
    )
    op.create_index(
        op.f("ix_tm_fuel_refills_freight_id"), "tm_fuel_refills", ["freight_id"], unique=False
    )
    op.create_index(
        op.f("ix_tm_fuel_refills_driver_id"), "tm_fuel_refills", ["driver_id"], unique=False
    )
    op.create_index(
        op.f("ix_tm_fuel_refills_truck_id"), "tm_fuel_refills", ["truck_id"], unique=False
    )
    op.create_index(
        op.f("ix_tm_fuel_refills_registrado_por_user_id"),
        "tm_fuel_refills",
        ["registrado_por_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tm_fuel_refills_data_abastecimento"),
        "tm_fuel_refills",
        ["data_abastecimento"],
        unique=False,
    )

    op.add_column(
        "tm_freight_notifications",
        sa.Column("fuel_refill_id", sa.UUID(), nullable=True),
    )
    op.alter_column(
        "tm_freight_notifications",
        "tracking_update_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.create_foreign_key(
        "fk_tm_freight_notifications_fuel_refill_id",
        "tm_freight_notifications",
        "tm_fuel_refills",
        ["fuel_refill_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_tm_freight_notifications_fuel_refill_id"),
        "tm_freight_notifications",
        ["fuel_refill_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tm_freight_notifications_fuel_refill_id"),
        table_name="tm_freight_notifications",
    )
    op.drop_constraint(
        "fk_tm_freight_notifications_fuel_refill_id",
        "tm_freight_notifications",
        type_="foreignkey",
    )
    op.drop_column("tm_freight_notifications", "fuel_refill_id")
    op.alter_column(
        "tm_freight_notifications",
        "tracking_update_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_table("tm_fuel_refills")
