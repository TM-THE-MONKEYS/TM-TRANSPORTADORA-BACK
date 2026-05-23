"""freight_notifications

Revision ID: a1b2c3d4e5f6
Revises: 3997a8e62d56
Create Date: 2026-05-23 01:00:00.000000+00:00

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "3997a8e62d56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE notificationtype AS ENUM ('tracking_occurrence');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.create_table(
        "tm_freight_notifications",
        sa.Column("freight_id", sa.UUID(), nullable=False),
        sa.Column("tracking_update_id", sa.UUID(), nullable=False),
        sa.Column(
            "tipo",
            postgresql.ENUM(
                "tracking_occurrence",
                name="notificationtype",
                create_type=False,
            ),
            nullable=False,
            server_default="tracking_occurrence",
        ),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("autor_user_id", sa.UUID(), nullable=True),
        sa.Column("autor_nome", sa.String(length=150), nullable=False),
        sa.Column("freight_code", sa.String(length=20), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["autor_user_id"], ["tm_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["freight_id"], ["tm_freights.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tracking_update_id"], ["tm_tracking_updates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tracking_update_id"),
    )
    op.create_index(
        op.f("ix_tm_freight_notifications_freight_id"),
        "tm_freight_notifications",
        ["freight_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tm_freight_notifications_freight_code"),
        "tm_freight_notifications",
        ["freight_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tm_freight_notifications_autor_user_id"),
        "tm_freight_notifications",
        ["autor_user_id"],
        unique=False,
    )

    op.create_table(
        "tm_notification_reads",
        sa.Column("notification_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["notification_id"], ["tm_freight_notifications.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["tm_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id", "user_id", name="uq_notification_read_user"
        ),
    )
    op.create_index(
        op.f("ix_tm_notification_reads_notification_id"),
        "tm_notification_reads",
        ["notification_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tm_notification_reads_user_id"),
        "tm_notification_reads",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("tm_notification_reads")
    op.drop_table("tm_freight_notifications")
    op.execute("DROP TYPE IF EXISTS notificationtype")
