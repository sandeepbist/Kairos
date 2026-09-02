"""batch events for SSE progress

Revision ID: 0002_batch_events
Revises: 0001_baseline
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_batch_events"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "batch_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_batch_events_batch_id", "batch_events", ["batch_id"])
    op.create_index("ix_batch_events_batch_seq", "batch_events", ["batch_id", "seq"])


def downgrade() -> None:
    op.drop_table("batch_events")
