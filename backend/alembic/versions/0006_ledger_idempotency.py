"""ledger idempotency reference

Revision ID: 0006_ledger_idempotency
Revises: 0005_operator_settings
Create Date: 2026-09-21

Adds task_ledger_tasks.external_ref (nullable, unique): the caller-
supplied dedup token carried from the execution idempotency key. A
crash between the ledger insert and the execution-log commit retries
into the original row instead of duplicating the task. Existing rows
keep NULL (no backfill: NULLs never collide under a unique index).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_ledger_idempotency"
down_revision: Union[str, None] = "0005_operator_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task_ledger_tasks",
        sa.Column("external_ref", sa.String(64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_task_ledger_tasks_external_ref",
        "task_ledger_tasks",
        ["external_ref"],
    )
    op.create_index(
        "ix_task_ledger_tasks_external_ref",
        "task_ledger_tasks",
        ["external_ref"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_ledger_tasks_external_ref", table_name="task_ledger_tasks")
    op.drop_constraint(
        "uq_task_ledger_tasks_external_ref", "task_ledger_tasks", type_="unique"
    )
    op.drop_column("task_ledger_tasks", "external_ref")
