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
    executed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    batch = relationship("BatchModel", back_populates="execution_logs")
    action_item = relationship("ActionItemModel", back_populates="execution_logs")

    __table_args__ = (
        Index("ix_execution_logs_hash_status", "idempotency_hash", "status"),
    )


class RoutingFeedbackModel(Base):
    """Routing feedback table: records user acceptance or override for Mem0 learning."""
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


class OAuthTokenModel(Base):
    """OAuth tokens table: stores encrypted credentials for external MCP servers."""
    __tablename__ = "oauth_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    provider = Column(String(50), nullable=False, unique=True, index=True)  # notion, jira, google_calendar
    access_token_enc = Column(Text, nullable=False)
    refresh_token_enc = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    scopes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
