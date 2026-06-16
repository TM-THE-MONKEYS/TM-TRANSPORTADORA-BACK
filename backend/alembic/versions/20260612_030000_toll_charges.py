"""toll charges and notification link

Revision ID: 20260612_030000
Revises: 20260523_020000
Create Date: 2026-06-12

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260612_030000"
down_revision: Union[str, None] = "20260523_020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tm_toll_charges",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("freight_id", sa.UUID(), nullable=False),
        sa.Column("driver_id", sa.UUID(), nullable=False),
        sa.Column("registrado_por_user_id", sa.UUID(), nullable=True),
        sa.Column("freight_cost_id", sa.UUID(), nullable=True),
        sa.Column("valor", sa.Float(), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("praca", sa.String(length=150), nullable=True),
        sa.Column("rodovia", sa.String(length=100), nullable=True),
        sa.Column("cidade", sa.String(length=100), nullable=True),
        sa.Column("estado", sa.String(length=2), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("data_pedagio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tm_tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("freight_cost_id"),
    )
    op.create_index(
        op.f("ix_tm_toll_charges_freight_id"), "tm_toll_charges", ["freight_id"], unique=False
    )
    op.create_index(
        op.f("ix_tm_toll_charges_driver_id"), "tm_toll_charges", ["driver_id"], unique=False
    )
    op.create_index(
        op.f("ix_tm_toll_charges_registrado_por_user_id"),
        "tm_toll_charges",
        ["registrado_por_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tm_toll_charges_data_pedagio"),
        "tm_toll_charges",
        ["data_pedagio"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tm_toll_charges_tenant_id"), "tm_toll_charges", ["tenant_id"], unique=False
    )

    # Add toll_charge_id to notifications table
    op.add_column(
        "tm_freight_notifications",
        sa.Column("toll_charge_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tm_freight_notifications_toll_charge_id",
        "tm_freight_notifications",
        "tm_toll_charges",
        ["toll_charge_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_tm_freight_notifications_toll_charge_id"),
        "tm_freight_notifications",
        ["toll_charge_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tm_freight_notifications_toll_charge_id"),
        table_name="tm_freight_notifications",
    )
    op.drop_constraint(
        "fk_tm_freight_notifications_toll_charge_id",
        "tm_freight_notifications",
        type_="foreignkey",
    )
    op.drop_column("tm_freight_notifications", "toll_charge_id")

    op.drop_index(op.f("ix_tm_toll_charges_tenant_id"), table_name="tm_toll_charges")
    op.drop_index(op.f("ix_tm_toll_charges_data_pedagio"), table_name="tm_toll_charges")
    op.drop_index(
        op.f("ix_tm_toll_charges_registrado_por_user_id"), table_name="tm_toll_charges"
    )
    op.drop_index(op.f("ix_tm_toll_charges_driver_id"), table_name="tm_toll_charges")
    op.drop_index(op.f("ix_tm_toll_charges_freight_id"), table_name="tm_toll_charges")
    op.drop_table("tm_toll_charges")
