"""merge alembic heads

Revision ID: 20260616_merge_heads
Revises: 001_multi_tenancy, 20260612_030000
Create Date: 2026-06-16

"""
from __future__ import annotations

from typing import Sequence, Union

revision: str = "20260616_merge_heads"
down_revision: Union[str, Sequence[str], None] = ("001_multi_tenancy", "20260612_030000")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
