"""Add trip odometer KM and pre-start checks to freights.

Revision ID: 20261109_freight_km
Revises: 20261107_freight_idx
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# alembic_version.version_num is VARCHAR(32) — keep revision id <= 32 chars.
revision: str = "20261109_freight_km"
down_revision: Union[str, Sequence[str], None] = "20261107_freight_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tm_freights", sa.Column("km_inicial", sa.Float(), nullable=True))
    op.add_column("tm_freights", sa.Column("km_final", sa.Float(), nullable=True))
    op.add_column(
        "tm_freights",
        sa.Column("km_inicial_registrado_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tm_freights",
        sa.Column("km_final_registrado_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tm_freights",
        sa.Column(
            "check_docs",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "tm_freights",
        sa.Column(
            "check_veiculo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "tm_freights",
        sa.Column(
            "check_carga",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("tm_freights", "check_carga")
    op.drop_column("tm_freights", "check_veiculo")
    op.drop_column("tm_freights", "check_docs")
    op.drop_column("tm_freights", "km_final_registrado_em")
    op.drop_column("tm_freights", "km_inicial_registrado_em")
    op.drop_column("tm_freights", "km_final")
    op.drop_column("tm_freights", "km_inicial")
