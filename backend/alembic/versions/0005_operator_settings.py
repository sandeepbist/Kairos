"""operator settings store

Revision ID: 0005_operator_settings
Revises: 0004_webhooks
Create Date: 2026-09-09

Operator-settable configuration (tool targets, execution mode) as a
key-value store so the Settings UI and the Temporal worker — separate
processes — read identical values, and so toggles survive restarts.
Env vars remain the deployment-time source: resolution order is
DB value → env var → default.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_operator_settings"
down_revision: Union[str, None] = "0004_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "operator_settings",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("operator_settings")
