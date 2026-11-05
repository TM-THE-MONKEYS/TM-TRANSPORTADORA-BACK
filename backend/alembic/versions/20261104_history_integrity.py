"""Integridade do histórico: datas reais, status history, soft delete em cascata.

Revision ID: 20261104_history_integrity
Revises: 20260820_finance_source_key

Backfill:
- lançamentos pago sem data_pagamento recebem a data de updated_at em America/Sao_Paulo
- fretes entregue sem data_entrega_real usam o evento_at do tracking entregue
  e, na falta dele, updated_at. A origem fica em data_entrega_real_origem.

Downgrade de data_pagamento não apaga datas: depois da migration não dá para
distinguir backfill de um pagamento lançado de verdade.
Downgrade de data_entrega_real só limpa linhas cuja origem foi o backfill
(tracking | updated_at).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261104_history_integrity"
down_revision: str | Sequence[str] | None = "20260820_finance_source_key"
branch_labels = None
depends_on = None

_CHILD_TABLES = (
    "tm_freight_stops",
    "tm_freight_costs",
    "tm_freight_attachments",
    "tm_fuel_refills",
    "tm_toll_charges",
    "tm_tracking_updates",
    "tm_freight_notifications",
    "tm_notification_reads",
)

_PARTIAL_UNIQUES: tuple[tuple[str, str, str, str], ...] = (
    (
        "uq_tm_fuel_refills_freight_cost_active",
        "tm_fuel_refills",
        "freight_cost_id",
        "freight_cost_id IS NOT NULL AND deleted_at IS NULL",
    ),
    (
        "uq_tm_toll_charges_freight_cost_active",
        "tm_toll_charges",
        "freight_cost_id",
        "freight_cost_id IS NOT NULL AND deleted_at IS NULL",
    ),
    (
        "uq_tm_freight_notifications_tracking_active",
        "tm_freight_notifications",
        "tracking_update_id",
        "tracking_update_id IS NOT NULL AND deleted_at IS NULL",
    ),
    (
        "uq_tm_freight_notifications_fuel_active",
        "tm_freight_notifications",
        "fuel_refill_id",
        "fuel_refill_id IS NOT NULL AND deleted_at IS NULL",
    ),
    (
        "uq_tm_freight_notifications_toll_active",
        "tm_freight_notifications",
        "toll_charge_id",
        "toll_charge_id IS NOT NULL AND deleted_at IS NULL",
    ),
)


def _drop_single_column_unique(table: str, column: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE r record;
            BEGIN
              FOR r IN
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                JOIN pg_attribute a
                  ON a.attrelid = t.oid AND a.attnum = ANY (c.conkey)
                WHERE n.nspname = current_schema()
                  AND t.relname = '{table}'
                  AND c.contype = 'u'
                  AND a.attname = '{column}'
                  AND cardinality(c.conkey) = 1
              LOOP
                EXECUTE format(
                  'ALTER TABLE %I DROP CONSTRAINT %I', '{table}', r.conname
                );
              END LOOP;
            END $$;
            """
        )
    )


def upgrade() -> None:
    op.add_column(
        "tm_freights",
        sa.Column("coletado_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tm_freights",
        sa.Column("data_entrega_real_origem", sa.String(length=20), nullable=True),
    )

    op.execute(
        """
        UPDATE tm_freights AS f
        SET data_entrega_real = t.evento_at,
            data_entrega_real_origem = 'tracking'
        FROM (
            SELECT DISTINCT ON (freight_id) freight_id, evento_at
            FROM tm_tracking_updates
            WHERE status = 'entregue'
            ORDER BY freight_id, evento_at DESC
        ) AS t
        WHERE f.id = t.freight_id
          AND f.status = 'entregue'
          AND f.data_entrega_real IS NULL
        """
    )
    op.execute(
        """
        UPDATE tm_freights
        SET data_entrega_real = updated_at,
            data_entrega_real_origem = 'updated_at'
        WHERE status = 'entregue'
          AND data_entrega_real IS NULL
        """
    )
    op.execute(
        """
        UPDATE tm_finance_entries
        SET data_pagamento = (updated_at AT TIME ZONE 'America/Sao_Paulo')::date
        WHERE status = 'pago'
          AND data_pagamento IS NULL
        """
    )

    for table in _CHILD_TABLES:
        op.add_column(
            table,
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(f"ix_{table}_deleted_at", table, ["deleted_at"])

    for _index, table, column, _predicate in _PARTIAL_UNIQUES:
        _drop_single_column_unique(table, column)

    op.execute(
        "ALTER TABLE tm_notification_reads "
        "DROP CONSTRAINT IF EXISTS uq_notification_read_user"
    )

    for index, table, column, predicate in _PARTIAL_UNIQUES:
        op.execute(
            f"CREATE UNIQUE INDEX {index} ON {table} ({column}) WHERE {predicate}"
        )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_notification_read_user_active
        ON tm_notification_reads (notification_id, user_id)
        WHERE deleted_at IS NULL
        """
    )

    op.create_table(
        "tm_status_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("from_status", sa.String(length=40), nullable=True),
        sa.Column("to_status", sa.String(length=40), nullable=False),
        sa.Column("changed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
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
            ["changed_by_user_id"], ["tm_users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tm_tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tm_status_history_tenant_id", "tm_status_history", ["tenant_id"]
    )
    op.create_index(
        "ix_tm_status_history_entity",
        "tm_status_history",
        ["tenant_id", "entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tm_status_history_entity", table_name="tm_status_history")
    op.drop_index("ix_tm_status_history_tenant_id", table_name="tm_status_history")
    op.drop_table("tm_status_history")

    op.execute("DROP INDEX IF EXISTS uq_notification_read_user_active")
    op.create_unique_constraint(
        "uq_notification_read_user",
        "tm_notification_reads",
        ["notification_id", "user_id"],
    )
    for index, table, column, _predicate in reversed(_PARTIAL_UNIQUES):
        op.execute(f"DROP INDEX IF EXISTS {index}")
        op.create_unique_constraint(f"{table}_{column}_key", table, [column])

    for table in reversed(_CHILD_TABLES):
        op.drop_index(f"ix_{table}_deleted_at", table_name=table)
        op.drop_column(table, "deleted_at")

    op.execute(
        """
        UPDATE tm_freights
        SET data_entrega_real = NULL
        WHERE data_entrega_real_origem IN ('tracking', 'updated_at')
        """
    )
    op.drop_column("tm_freights", "data_entrega_real_origem")
    op.drop_column("tm_freights", "coletado_em")
