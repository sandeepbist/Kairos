"""SQLAlchemy database models for Kairos."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BatchModel(Base):
    """Batches table: tracks incoming ingestion sessions and workflow status."""
    __tablename__ = "batches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_type = Column(String(50), nullable=False, default="meeting_transcript")
    raw_text = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="processing", index=True)
    token_count = Column(Integer, nullable=True)
    temporal_workflow_id = Column(String(100), nullable=True, index=True)
    # Multi-user prep: nullable ownership dimension (see migration 0003).
    user_id = Column(String(36), nullable=True, index=True)
    org_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    action_items = relationship(
        "ActionItemModel",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="ActionItemModel.created_at",
    )
    execution_logs = relationship(
        "ExecutionLogModel",
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class ActionItemModel(Base):
    """Action items table: extracted candidates, decisions, and execution status."""
    __tablename__ = "action_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    batch_id = Column(String(36), ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(Text, nullable=False)
    suggested_tool = Column(String(50), nullable=False, index=True)
    final_tool = Column(String(50), nullable=True)
    tool_payload = Column(JSON, nullable=False, default=dict)
    source_snippet = Column(Text, nullable=False)
    speaker = Column(String(100), nullable=True)
    suggested_assignee = Column(String(100), nullable=True)
    actionability_type = Column(String(30), nullable=False, default="task")
    priority = Column(String(20), nullable=False, default="medium")
    confidence = Column(Float, nullable=False, default=0.8)
    status = Column(String(30), nullable=False, default="pending", index=True)
    external_url = Column(String(500), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    user_id = Column(String(36), nullable=True)
    org_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    batch = relationship("BatchModel", back_populates="action_items")
    execution_logs = relationship("ExecutionLogModel", back_populates="action_item", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_action_items_batch_status", "batch_id", "status"),
    )


class ExecutionLogModel(Base):
    """Execution log table: audit history, deduplication hashes, and telemetry."""
    __tablename__ = "execution_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    item_id = Column(String(36), ForeignKey("action_items.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(String(36), ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    tool = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False, default="success")  # success, failed, skipped_duplicate
    idempotency_hash = Column(String(64), nullable=False, index=True)
    external_url = Column(String(500), nullable=True)
    item_description = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    user_id = Column(String(36), nullable=True)
    org_id = Column(String(36), nullable=True)
    executed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    batch = relationship("BatchModel", back_populates="execution_logs")
    action_item = relationship("ActionItemModel", back_populates="execution_logs")

    __table_args__ = (
        Index("ix_execution_logs_hash_status", "idempotency_hash", "status"),
    )


class RoutingFeedbackModel(Base):
    """Routing feedback table: records user acceptance or override for routing-memory learning."""
    __tablename__ = "routing_feedback"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    item_id = Column(String(36), nullable=False, index=True)
    batch_id = Column(String(36), nullable=False, index=True)
    item_description = Column(Text, nullable=False)
    suggested_tool = Column(String(50), nullable=False)
    final_tool = Column(String(50), nullable=False)
    was_overridden = Column(Boolean, nullable=False, default=False)
    # Embedding of item_description for semantic neighbor matching.
    # JSONB float array rather than a pgvector column: embedding dimension
    # varies by provider (Gemini 768 / OpenAI 1536) and in-process cosine
    # over the recent window is sub-5ms at operator scale.
    embedding = Column(JSON, nullable=True)
    user_id = Column(String(36), nullable=True)
    org_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class TaskLedgerModel(Base):
    """Custom internal Task Ledger table: standalone fallback task management."""
    __tablename__ = "task_ledger_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    notes = Column(Text, nullable=False, default="")
    priority = Column(String(20), nullable=False, default="medium")
    due_date = Column(String(50), nullable=True)
    status = Column(String(30), nullable=False, default="open", index=True)  # open, completed, deleted
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class BatchEventModel(Base):
    """Progress events for a batch, streamed to the review UI over SSE.

    Written at pipeline milestones (ingested, chunk k/N extracted,
    routed, persisted, awaiting review); the SSE endpoint tails rows
    in creation order. Durable by construction — events live in
    Postgres, so a refresh replays them.
    """
    __tablename__ = "batch_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    batch_id = Column(String(36), ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # stage name
    message = Column(Text, nullable=False, default="")
    seq = Column(Integer, nullable=False, default=0)  # monotonic per batch
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class OAuthTokenModel(Base):
    """OAuth tokens table: stores encrypted credentials for external MCP servers."""
    __tablename__ = "oauth_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    provider = Column(String(50), nullable=False, unique=True, index=True)  # notion, jira, google_calendar
    access_token_enc = Column(Text, nullable=False)
    refresh_token_enc = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    scopes = Column(Text, nullable=True)
    # Multi-user prep: per-user vault rows land as (user_id, provider)
    # when per-user OAuth exists; the unique constraint moves then.
    user_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class WebhookEndpointModel(Base):
    """Outbound webhook destination (Standard Webhooks). The secret is
    Fernet-encrypted like OAuth tokens; previous_secret_enc stays
    signable for 24h after rotation so receivers swap keys without a
    delivery gap (spec: multi-key signing)."""
    __tablename__ = "webhook_endpoints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    url = Column(String(2048), nullable=False)
    description = Column(String(200), nullable=False, default="")
    secret_enc = Column(Text, nullable=False)
    previous_secret_enc = Column(Text, nullable=True)
    rotated_at = Column(DateTime(timezone=True), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    event_types = Column(JSON, nullable=False, default=lambda: ["*"])  # "*" = all events
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    deliveries = relationship(
        "WebhookDeliveryModel", back_populates="endpoint", cascade="all, delete-orphan"
    )


class WebhookDeliveryModel(Base):
    """One event to one endpoint. msg_id is minted once and reused for
    every attempt so receivers can dedupe retries (spec requirement)."""
    __tablename__ = "webhook_deliveries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    endpoint_id = Column(
        String(36), ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    msg_id = Column(String(64), nullable=False)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)  # full envelope {"type","timestamp","data"}
    status = Column(String(20), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_response_code = Column(Integer, nullable=True)
    last_error = Column(String(500), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    endpoint = relationship("WebhookEndpointModel", back_populates="deliveries")
    __table_args__ = (
        Index("ix_webhook_deliveries_endpoint_created", "endpoint_id", "created_at"),
    )
