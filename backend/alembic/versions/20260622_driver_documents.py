"""driver documents + foto_url

Revision ID: 20260622_driver_documents
Revises: 20260621_truck_implements
Create Date: 2026-06-22

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260622_driver_documents"
down_revision: Union[str, Sequence[str], None] = "20260621_truck_implements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tm_drivers",
        sa.Column("foto_url", sa.String(length=500), nullable=True),
    )
    op.create_table(
        "tm_driver_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("driver_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("titulo", sa.String(length=150), nullable=True),
        sa.Column("nome_arquivo", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tm_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["driver_id"], ["tm_drivers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tm_driver_documents_driver_id", "tm_driver_documents", ["driver_id"])
    op.create_index("ix_tm_driver_documents_deleted_at", "tm_driver_documents", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_tm_driver_documents_deleted_at", table_name="tm_driver_documents")
    op.drop_index("ix_tm_driver_documents_driver_id", table_name="tm_driver_documents")
    op.drop_table("tm_driver_documents")
    op.drop_column("tm_drivers", "foto_url")
