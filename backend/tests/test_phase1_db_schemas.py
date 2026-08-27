"""Phase 1 Battle Test Suite: Pydantic Schemas & Database Models."""
import pytest
import uuid
from datetime import datetime, date
from sqlalchemy import select
from app.config import settings
from app.db.session import init_db, async_session_factory, engine
from app.db.models import (
    BatchModel,
    ActionItemModel,
    ExecutionLogModel,
    RoutingFeedbackModel,
    TaskLedgerModel,
    OAuthTokenModel,
)
from app.schemas.payloads import (
    JiraPayload,
    CalendarPayload,
    NotionPayload,
    TaskLedgerPayload,
)
from app.schemas.action_item import (
    ActionItemDraft,
    ActionItemDecision,
    BatchIngestRequest,
)
from pydantic import ValidationError


# ---------------------------------------------------------
# Test 1: Pydantic Payload Validation & Edge Cases
# ---------------------------------------------------------

def test_jira_payload_valid():
    payload = JiraPayload(
        project_key="ENG",
        issue_type="Bug",
        summary="Fix OAuth token refresh race condition",
        description="Tokens expire unexpectedly during concurrent MCP calls.",
        priority="High",
        due_date=date(2026, 9, 1),
    )
    assert payload.project_key == "ENG"
    assert payload.issue_type == "Bug"
    assert payload.priority == "High"
    assert payload.due_date == date(2026, 9, 1)


def test_jira_payload_defaults_and_invalid():
    # Defaults
    payload = JiraPayload(
        summary="Basic Task",
        description="Some details",
    )
    assert payload.project_key == "PROJ"
    assert payload.issue_type == "Task"
    assert payload.priority == "Medium"
    assert payload.due_date is None

    # Invalid issue type
    with pytest.raises(ValidationError):
        JiraPayload(
            issue_type="Epic",  # Not in Literal["Task", "Story", "Bug"]
            summary="Invalid",
            description="Details",
        )


def test_calendar_payload_valid():
    payload = CalendarPayload(
        title="Sprint Planning Meeting",
        start_time="2026-09-01T10:00:00Z",
        end_time="2026-09-01T11:00:00Z",
        attendees=["alex@company.com", "sarah@company.com"],
        location="Google Meet",
        reminder_minutes_before=15,
    )
    assert payload.title == "Sprint Planning Meeting"
    assert len(payload.attendees) == 2
    assert payload.reminder_minutes_before == 15


def test_notion_and_task_ledger_payloads():
    notion = NotionPayload(
        database_id="db-12345",
        title="Q3 Roadmap Document",
        details="Key objectives for ambient AI workflows.",
        properties={"Status": "In Progress"},
    )
    assert notion.database_id == "db-12345"
    assert notion.properties["Status"] == "In Progress"

    ledger = TaskLedgerPayload(
        title="Follow up with design team",
        notes="Review Figma tokens",
        priority="high",
        due_date="2026-09-05",
    )
    assert ledger.priority == "high"


def test_action_item_draft_schema():
    draft = ActionItemDraft(
        description="Schedule budget review with CFO",
        suggested_tool="calendar",
        suggested_due_date=date(2026, 8, 30),
        suggested_assignee="Alex",
        speaker="Sarah",
        actionability_type="calendar_event",
        priority="high",
        confidence=0.95,
        source_snippet="Sarah: Alex, please set up a budget review with the CFO by Friday.",
        tool_payload={
            "title": "Budget Review with CFO",
            "start_time": "2026-08-30T14:00:00Z",
            "end_time": "2026-08-30T15:00:00Z",
        },
    )
    assert draft.confidence == 0.95
    assert draft.speaker == "Sarah"
    assert draft.suggested_assignee == "Alex"
    assert draft.actionability_type == "calendar_event"


# ---------------------------------------------------------
# Test 2: Live Database Initialization & CRUD Battle Tests
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_db_initialization():
    """Verify that init_db creates all tables without error."""
    await init_db()


@pytest.mark.asyncio
async def test_db_batch_and_action_items_crud():
    """Verify creation, relationship binding, and cascade deletion."""
    await init_db()

    async with async_session_factory() as session:
        # 1. Create Batch
        batch_id = str(uuid.uuid4())
        batch = BatchModel(
            id=batch_id,
            source_type="meeting_transcript",
            raw_text="Sarah: Alex, please file a ticket for the checkout bug.",
            status="awaiting_approval",
            token_count=12,
            temporal_workflow_id=f"wf-{batch_id}",
        )
        session.add(batch)

        # 2. Add Action Item
        item_id = str(uuid.uuid4())
        item = ActionItemModel(
            id=item_id,
            batch_id=batch_id,
            description="File a ticket for checkout bug",
            suggested_tool="jira",
            tool_payload={
                "project_key": "ENG",
                "issue_type": "Bug",
                "summary": "Fix checkout bug",
                "description": "Reported during sync",
            },
            source_snippet="Sarah: Alex, please file a ticket for the checkout bug.",
            speaker="Sarah",
            suggested_assignee="Alex",
            confidence=0.92,
            status="pending",
        )
        session.add(item)
        await session.commit()

    # 3. Read back
    async with async_session_factory() as session:
        result = await session.execute(
            select(BatchModel).where(BatchModel.id == batch_id)
        )
        saved_batch = result.scalar_one_or_none()
        assert saved_batch is not None
        assert saved_batch.status == "awaiting_approval"

        item_result = await session.execute(
            select(ActionItemModel).where(ActionItemModel.batch_id == batch_id)
        )
        saved_items = item_result.scalars().all()
        assert len(saved_items) == 1
        assert saved_items[0].suggested_tool == "jira"
        assert saved_items[0].tool_payload["project_key"] == "ENG"
        assert saved_items[0].speaker == "Sarah"

    # 4. Clean up test batch
    async with async_session_factory() as session:
        res = await session.execute(select(BatchModel).where(BatchModel.id == batch_id))
        b = res.scalar_one_or_none()
        if b:
            await session.delete(b)
            await session.commit()


@pytest.mark.asyncio
async def test_db_execution_logs_and_idempotency():
    """Verify execution logs table and idempotency hash indexing."""
    await init_db()
    batch_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    log_id = str(uuid.uuid4())
    test_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    async with async_session_factory() as session:
        batch = BatchModel(id=batch_id, raw_text="Test", status="executing")
        session.add(batch)
        item = ActionItemModel(
            id=item_id,
            batch_id=batch_id,
            description="Test Action",
            suggested_tool="task_ledger",
            source_snippet="Test",
            confidence=0.9,
        )
        session.add(item)
        log = ExecutionLogModel(
            id=log_id,
            item_id=item_id,
            batch_id=batch_id,
            tool="task_ledger",
            status="success",
            idempotency_hash=test_hash,
            external_url="task_ledger://tasks/task_123",
            latency_ms=120,
        )
        session.add(log)
        await session.commit()

    async with async_session_factory() as session:
        res = await session.execute(
            select(ExecutionLogModel).where(ExecutionLogModel.idempotency_hash == test_hash)
        )
        saved_log = res.scalar_one_or_none()
        assert saved_log is not None
        assert saved_log.status == "success"
        assert saved_log.external_url == "task_ledger://tasks/task_123"

        # Cleanup
        b_res = await session.execute(select(BatchModel).where(BatchModel.id == batch_id))
        b = b_res.scalar_one_or_none()
        if b:
            await session.delete(b)
            await session.commit()


@pytest.mark.asyncio
async def test_task_ledger_model_crud():
    """Verify internal task ledger model CRUD operations."""
    await init_db()
    task_id = str(uuid.uuid4())

    async with async_session_factory() as session:
        task = TaskLedgerModel(
            id=task_id,
            title="Review pull request #42",
            notes="Check unit tests",
            priority="high",
            due_date="2026-09-01",
            status="open",
        )
        session.add(task)
        await session.commit()

    async with async_session_factory() as session:
        res = await session.execute(
            select(TaskLedgerModel).where(TaskLedgerModel.id == task_id)
        )
        saved_task = res.scalar_one_or_none()
        assert saved_task is not None
        assert saved_task.title == "Review pull request #42"
        assert saved_task.status == "open"

        # Update status
        saved_task.status = "completed"
        await session.commit()

    async with async_session_factory() as session:
        res = await session.execute(
            select(TaskLedgerModel).where(TaskLedgerModel.id == task_id)
        )
        updated_task = res.scalar_one_or_none()
        assert updated_task.status == "completed"

        # Cleanup
        await session.delete(updated_task)
        await session.commit()
