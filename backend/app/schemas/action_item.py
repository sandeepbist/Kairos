"""Core action item, batch, and decision models."""
from datetime import datetime, date
from typing import Literal, Any, Union
import uuid
from pydantic import BaseModel, Field
from .payloads import (
    JiraPayload,
    CalendarPayload,
    NotionPayload,
    TaskLedgerPayload,
    ToolPayloadUnion,
)

SourceType = Literal["meeting_transcript", "email_thread", "slack_conversation", "general_notes"]
TargetTool = Literal["notion", "jira", "calendar", "task_ledger"]
ActionabilityType = Literal["task", "decision", "fyi", "calendar_event"]
PriorityLevel = Literal["low", "medium", "high"]
ItemStatus = Literal["pending", "approved", "rejected", "modified_approved", "executed", "failed"]
BatchStatus = Literal["processing", "awaiting_approval", "executing", "completed", "failed", "expired"]
DecisionAction = Literal["APPROVE", "MODIFY_AND_APPROVE", "REJECT"]


class ActionItemDraft(BaseModel):
    """Raw structured candidate extracted by LLM from source text."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Client/session item ID")
    description: str = Field(..., description="Clear, actionable task description")
    suggested_tool: TargetTool = Field(..., description="Target tool proposed by reasoning & memory")
    suggested_due_date: date | None = Field(default=None, description="Inferred or explicitly mentioned due date")
    suggested_assignee: str | None = Field(default=None, description="Extracted owner or assignee if mentioned")
    speaker: str | None = Field(default=None, description="Speaker name if identified in source, null otherwise")
    actionability_type: ActionabilityType = Field(default="task", description="Classification of the extracted item")
    priority: PriorityLevel = Field(default="medium", description="Priority level")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    source_snippet: str = Field(..., description="Exact quote/lines from source text for human verification")
    tool_payload: dict[str, Any] = Field(default_factory=dict, description="Pre-filled tool payload")


class ActionItem(BaseModel):
    """Persisted Action Item entity."""
    id: str
    batch_id: str
    description: str
    suggested_tool: TargetTool
    final_tool: TargetTool | None = None
    tool_payload: dict[str, Any]
    source_snippet: str
    speaker: str | None = None
    suggested_assignee: str | None = None
    actionability_type: ActionabilityType = "task"
    priority: PriorityLevel = "medium"
    confidence: float
    status: ItemStatus = "pending"
    external_url: str | None = None
    rejection_reason: str | None = None
    executed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ActionItemDecision(BaseModel):
    """Human-in-the-loop decision per action item."""
    item_id: str
    decision: DecisionAction = "APPROVE"
    action: DecisionAction | None = None
    override_tool: TargetTool | None = None
    modified_payload: dict[str, Any] | None = None
    rejection_reason: str | None = None

    @classmethod
    def model_validate(cls, obj: Any, **kwargs):
        if isinstance(obj, dict):
            if "action" in obj and ("decision" not in obj or not obj.get("decision")):
                obj["decision"] = obj["action"]
            elif "decision" in obj and ("action" not in obj or not obj.get("action")):
                obj["action"] = obj["decision"]
        return super().model_validate(obj, **kwargs)


class ActionItemApprovalRequest(BaseModel):
    """Payload received when user submits batch decisions."""
    batch_id: str
    decisions: list[ActionItemDecision]


class BatchIngestRequest(BaseModel):
    """Incoming request to ingest text and start extraction workflow."""
    raw_text: str = Field(..., min_length=10, description="Raw unstructured text")
    source_type: SourceType = Field(default="meeting_transcript", description="Type of unstructured input")


class BatchStatusResponse(BaseModel):
    """Response returned for batch queries."""
    batch_id: str
    status: BatchStatus
    source_type: SourceType
    raw_text: str
    token_count: int | None = None
    items: list[ActionItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None
    temporal_workflow_id: str | None = None


class ExecutionHistoryItem(BaseModel):
    """Execution history log record with links and performance telemetry."""
    id: str
    item_id: str
    batch_id: str
    tool: TargetTool
    status: Literal["success", "failed", "skipped_duplicate"]
    idempotency_hash: str
    external_url: str | None = None
    item_description: str | None = None
    executed_at: datetime
    latency_ms: int | None = None
    error: str | None = None
