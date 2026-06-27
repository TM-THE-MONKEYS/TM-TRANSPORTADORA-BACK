"""freight stops, fixed expenses, implement dimensions

Revision ID: 20260623_backend_features
Revises: 20260622_driver_documents
Create Date: 2026-06-23

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_backend_features"
down_revision: Union[str, Sequence[str], None] = "20260622_driver_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

fixed_expense_frequency = sa.Enum(
    "mensal",
    "trimestral",
    "semestral",
    "anual",
    name="fixedexpensefrequency",
)


def upgrade() -> None:
    fixed_expense_frequency.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tm_freight_stops",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("freight_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("cep", sa.String(length=9), nullable=True),
        sa.Column("street", sa.String(length=255), nullable=True),
        sa.Column("neighborhood", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("cargo_description", sa.Text(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tm_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["freight_id"], ["tm_freights.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("freight_id", "sequence", name="uq_freight_stop_sequence"),
    )
    op.create_index("ix_tm_freight_stops_freight_id", "tm_freight_stops", ["freight_id"])
    op.create_index("ix_tm_freight_stops_tenant_id", "tm_freight_stops", ["tenant_id"])

    op.create_table(
        "tm_fixed_expenses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("categoria", sa.String(length=100), nullable=False),
        sa.Column("valor", sa.Float(), nullable=False),
        sa.Column("frequencia", fixed_expense_frequency, nullable=False, server_default="mensal"),
        sa.Column("dia_vencimento", sa.Integer(), nullable=True),
        sa.Column("total_parcelas", sa.Integer(), nullable=True),
        sa.Column("parcelas_lancadas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("data_inicio", sa.Date(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tm_tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tm_fixed_expenses_tenant_id", "tm_fixed_expenses", ["tenant_id"])
    op.create_index("ix_tm_fixed_expenses_categoria", "tm_fixed_expenses", ["categoria"])
    op.create_index("ix_tm_fixed_expenses_ativo", "tm_fixed_expenses", ["ativo"])
    op.create_index("ix_tm_fixed_expenses_deleted_at", "tm_fixed_expenses", ["deleted_at"])

    op.add_column("tm_truck_implements", sa.Column("length_m", sa.Float(), nullable=True))
    op.add_column("tm_truck_implements", sa.Column("width_m", sa.Float(), nullable=True))
    op.add_column("tm_truck_implements", sa.Column("height_m", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("tm_truck_implements", "height_m")
    op.drop_column("tm_truck_implements", "width_m")
    op.drop_column("tm_truck_implements", "length_m")

    op.drop_index("ix_tm_fixed_expenses_deleted_at", table_name="tm_fixed_expenses")
    op.drop_index("ix_tm_fixed_expenses_ativo", table_name="tm_fixed_expenses")
    op.drop_index("ix_tm_fixed_expenses_categoria", table_name="tm_fixed_expenses")
    op.drop_index("ix_tm_fixed_expenses_tenant_id", table_name="tm_fixed_expenses")
    op.drop_table("tm_fixed_expenses")

    op.drop_index("ix_tm_freight_stops_tenant_id", table_name="tm_freight_stops")
    op.drop_index("ix_tm_freight_stops_freight_id", table_name="tm_freight_stops")
    op.drop_table("tm_freight_stops")

    fixed_expense_frequency.drop(op.get_bind(), checkfirst=True)
