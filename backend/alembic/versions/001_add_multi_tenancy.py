"""Add multi-tenancy: tm_tenants table + tenant_id column on all tables.

Revision ID: 001_multi_tenancy
Revises: (initial)
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "001_multi_tenancy"
down_revision = None
branch_labels = None
depends_on = None

DEFAULT_TENANT_ID = str(uuid.uuid4())

TABLES_WITH_TENANT = [
    "tm_users",
    "tm_refresh_tokens",
    "tm_drivers",
    "tm_trucks",
    "tm_freights",
    "tm_freight_costs",
    "tm_freight_attachments",
    "tm_clients",
    "tm_finance_entries",
    "tm_fuel_refills",
    "tm_tracking_updates",
    "tm_freight_notifications",
    "tm_notification_reads",
    "tm_maintenance",
]


def upgrade() -> None:
    op.create_table(
        "tm_tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("documento", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("plano", sa.String(50), nullable=False, server_default=sa.text("'free'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.execute(
        sa.text(
            "INSERT INTO tm_tenants (id, nome, documento) VALUES (:id, :nome, :doc)"
        ).bindparams(
            id=DEFAULT_TENANT_ID,
            nome="Transportadora TM",
            doc=None,
        )
    )

    for table in TABLES_WITH_TENANT:
        op.add_column(table, sa.Column("tenant_id", UUID(as_uuid=True), nullable=True))

        op.execute(
            sa.text(f"UPDATE {table} SET tenant_id = :tid").bindparams(tid=DEFAULT_TENANT_ID)  # noqa: S608
        )

        op.alter_column(table, "tenant_id", nullable=False)

        op.create_foreign_key(
            f"fk_{table}_tenant",
            table,
            "tm_tenants",
            ["tenant_id"],
            ["id"],
        )
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])


def downgrade() -> None:
    for table in reversed(TABLES_WITH_TENANT):
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_constraint(f"fk_{table}_tenant", table, type_="foreignkey")
        op.drop_column(table, "tenant_id")

    op.drop_table("tm_tenants")
