"""driver FK set null on fuel/toll + snapshot nome

Revision ID: 20260617_driver_fk_set_null
Revises: 20260616_merge_heads
Create Date: 2026-06-17

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260617_driver_fk_set_null"
down_revision: Union[str, Sequence[str], None] = "20260616_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tm_fuel_refills",
        sa.Column("driver_nome", sa.String(length=150), nullable=True),
    )
    op.add_column(
        "tm_toll_charges",
        sa.Column("driver_nome", sa.String(length=150), nullable=True),
    )

    op.execute(
        """
        UPDATE tm_fuel_refills fr
        SET driver_nome = d.nome
        FROM tm_drivers d
        WHERE fr.driver_id = d.id AND fr.driver_nome IS NULL
        """
    )
    op.execute(
        """
        UPDATE tm_toll_charges tc
        SET driver_nome = d.nome
        FROM tm_drivers d
        WHERE tc.driver_id = d.id AND tc.driver_nome IS NULL
        """
    )

    op.drop_constraint(
        "tm_fuel_refills_driver_id_fkey", "tm_fuel_refills", type_="foreignkey"
    )
    op.create_foreign_key(
        "tm_fuel_refills_driver_id_fkey",
        "tm_fuel_refills",
        "tm_drivers",
        ["driver_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("tm_fuel_refills", "driver_id", existing_type=sa.UUID(), nullable=True)

    op.drop_constraint(
        "tm_toll_charges_driver_id_fkey", "tm_toll_charges", type_="foreignkey"
    )
    op.create_foreign_key(
        "tm_toll_charges_driver_id_fkey",
        "tm_toll_charges",
        "tm_drivers",
        ["driver_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("tm_toll_charges", "driver_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("tm_toll_charges", "driver_id", existing_type=sa.UUID(), nullable=False)
    op.drop_constraint(
        "tm_toll_charges_driver_id_fkey", "tm_toll_charges", type_="foreignkey"
    )
    op.create_foreign_key(
        "tm_toll_charges_driver_id_fkey",
        "tm_toll_charges",
        "tm_drivers",
        ["driver_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column("tm_toll_charges", "driver_nome")

    op.alter_column("tm_fuel_refills", "driver_id", existing_type=sa.UUID(), nullable=False)
    op.drop_constraint(
        "tm_fuel_refills_driver_id_fkey", "tm_fuel_refills", type_="foreignkey"
    )
    op.create_foreign_key(
        "tm_fuel_refills_driver_id_fkey",
        "tm_fuel_refills",
        "tm_drivers",
        ["driver_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column("tm_fuel_refills", "driver_nome")
