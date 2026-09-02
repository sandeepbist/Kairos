"""multi-user prep: nullable user_id/org_id on core tables

Revision ID: 0003_user_prep
Revises: 0002_batch_events
Create Date: 2026-09-02

Prep only: Kairos remains single-operator. These nullable columns give
every batch, item, decision, and credential an ownership dimension
before any multi-user feature exists, so the eventual migration is
backfilling values instead of restructuring tables under live traffic.
All queries ignore the columns until they are used.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_user_prep"
down_revision: Union[str, None] = "0002_batch_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("batches", "action_items", "execution_logs", "routing_feedback"):
        op.add_column(table, sa.Column("user_id", sa.String(36), nullable=True))
        op.add_column(table, sa.Column("org_id", sa.String(36), nullable=True))
    # oauth_tokens already has provider uniqueness; ownership lands when
    # per-user vaults exist (provider uniqueness becomes (user, provider)).
    op.add_column("oauth_tokens", sa.Column("user_id", sa.String(36), nullable=True))
    op.create_index("ix_batches_user_id", "batches", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_batches_user_id", table_name="batches")
    op.drop_column("oauth_tokens", "user_id")
    for table in ("routing_feedback", "execution_logs", "action_items", "batches"):
        op.drop_column(table, "org_id")
        op.drop_column(table, "user_id")
