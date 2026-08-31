"""Kairos baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-31

Full schema for a fresh deployment: batches, action_items,
execution_logs, routing_feedback (with semantic embedding column),
task_ledger_tasks, oauth_tokens, and their indexes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector is optional (used only if semantic search migrates to
    # vector columns later); tolerate its absence on plain Postgres.
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception:
        pass

    op.create_table(
        "batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="meeting_transcript"),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="processing"),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("temporal_workflow_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_batches_status", "batches", ["status"])
    op.create_index("ix_batches_temporal_workflow_id", "batches", ["temporal_workflow_id"])

    op.create_table(
        "action_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("suggested_tool", sa.String(50), nullable=False),
        sa.Column("final_tool", sa.String(50), nullable=True),
        sa.Column("tool_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("source_snippet", sa.Text(), nullable=False),
        sa.Column("speaker", sa.String(100), nullable=True),
        sa.Column("suggested_assignee", sa.String(100), nullable=True),
        sa.Column("actionability_type", sa.String(30), nullable=False, server_default="task"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("external_url", sa.String(500), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_action_items_batch_id", "action_items", ["batch_id"])
    op.create_index("ix_action_items_status", "action_items", ["status"])
    op.create_index("ix_action_items_suggested_tool", "action_items", ["suggested_tool"])
    op.create_index("ix_action_items_batch_status", "action_items", ["batch_id", "status"])

    op.create_table(
        "execution_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("action_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="success"),
        sa.Column("idempotency_hash", sa.String(64), nullable=False),
        sa.Column("external_url", sa.String(500), nullable=True),
        sa.Column("item_description", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_execution_logs_item_id", "execution_logs", ["item_id"])
    op.create_index("ix_execution_logs_batch_id", "execution_logs", ["batch_id"])
    op.create_index("ix_execution_logs_idempotency_hash", "execution_logs", ["idempotency_hash"])
    op.create_index("ix_execution_logs_hash_status", "execution_logs", ["idempotency_hash", "status"])

    op.create_table(
        "routing_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_id", sa.String(36), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("item_description", sa.Text(), nullable=False),
        sa.Column("suggested_tool", sa.String(50), nullable=False),
        sa.Column("final_tool", sa.String(50), nullable=False),
        sa.Column("was_overridden", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        # Embedding of item_description for semantic neighbor matching.
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_routing_feedback_item_id", "routing_feedback", ["item_id"])
    op.create_index("ix_routing_feedback_batch_id", "routing_feedback", ["batch_id"])

    op.create_table(
        "task_ledger_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("due_date", sa.String(50), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_task_ledger_tasks_status", "task_ledger_tasks", ["status"])

    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("access_token_enc", sa.Text(), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_oauth_tokens_provider", "oauth_tokens", ["provider"])
    op.create_unique_constraint("uq_oauth_tokens_provider", "oauth_tokens", ["provider"])


def downgrade() -> None:
    op.drop_table("oauth_tokens")
    op.drop_table("task_ledger_tasks")
    op.drop_table("routing_feedback")
    op.drop_table("execution_logs")
    op.drop_table("action_items")
    op.drop_table("batches")
