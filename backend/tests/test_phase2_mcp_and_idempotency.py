"""Phase 2 Battle Test Suite: Custom Task Ledger MCP Server & MCP Client Manager."""
import pytest
import uuid
from sqlalchemy import select
from app.db.session import init_db, async_session_factory
from app.db.models import BatchModel, ActionItemModel, ExecutionLogModel, TaskLedgerModel
from app.mcp.servers.task_ledger import (
    task_ledger_server,
    create_task,
    list_tasks,
    complete_task,
    delete_task,
)
from app.mcp.client_manager import McpClientManager, mcp_client_manager


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


# ---------------------------------------------------------
# Test 1: Task Ledger FastMCP Server Tool Invocations
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_task_ledger_mcp_server_tools():
    """Verify create, list, complete, and delete tools on Task Ledger MCP server."""
    # 1. Create task
    task = await create_task(
        title="Implement OAuth Vault Middleware",
        notes="Encrypt with Fernet key",
        priority="high",
        due_date="2026-09-01",
    )
    assert task["id"] is not None
    assert task["title"] == "Implement OAuth Vault Middleware"
    assert task["status"] == "open"
    assert "task_ledger://tasks/" in task["external_url"]
    task_id = task["id"]

    # 2. List tasks
    all_tasks = await list_tasks()
    assert any(t["id"] == task_id for t in all_tasks)

    # 3. Complete task
    completed = await complete_task(task_id)
    assert completed["status"] == "completed"

    # 4. List open tasks only
    open_tasks = await list_tasks(status="open")
    assert not any(t["id"] == task_id for t in open_tasks)

    # 5. Delete task
    deleted = await delete_task(task_id)
    assert deleted["status"] == "deleted"


# ---------------------------------------------------------
# Test 2: Connector Invocations (All 4 tools in Sandbox Mode)
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_notion_connector_execution():
    connector = mcp_client_manager.get_connector("notion")
    payload = {
        "title": "Weekly Engineering Sync Notes",
        "database_id": "db_roadmap_123",
        "details": "Decisions on architecture and MCP rollout.",
    }
    result = await connector.execute(payload, sandbox_mode=True)
    assert result.status == "success"
    assert result.tool == "notion"
    assert "notion.so" in result.external_url
    assert result.raw_response["mode"] == "sandbox"


@pytest.mark.asyncio
async def test_jira_connector_execution():
    connector = mcp_client_manager.get_connector("jira")
    payload = {
        "project_key": "SEC",
        "summary": "Implement Token Refresh Guard",
        "issue_type": "Bug",
        "priority": "High",
    }
    result = await connector.execute(payload, sandbox_mode=True)
    assert result.status == "success"
    assert result.tool == "jira"
    assert "SEC-" in result.external_url
    assert "atlassian.net" in result.external_url


@pytest.mark.asyncio
async def test_calendar_connector_execution():
    connector = mcp_client_manager.get_connector("calendar")
    payload = {
        "title": "Post-Mortem: Memory Override Behavior",
        "start_time": "2026-09-02T15:00:00Z",
        "end_time": "2026-09-02T16:00:00Z",
        "attendees": ["lead@company.com"],
    }
    result = await connector.execute(payload, sandbox_mode=True)
    assert result.status == "success"
    assert result.tool == "calendar"
    assert "calendar.google.com" in result.external_url


@pytest.mark.asyncio
async def test_task_ledger_connector_execution():
    connector = mcp_client_manager.get_connector("task_ledger")
    payload = {
        "title": "Clean up temporary test artifacts",
        "notes=" : "Ensure zero clutter",
        "priority": "low",
    }
    result = await connector.execute(payload, sandbox_mode=True)
    assert result.status == "success"
    assert result.tool == "task_ledger"
    assert "task_ledger://tasks/" in result.external_url


# ---------------------------------------------------------
# Test 3: Idempotency & Deduplication Engine Battle Test
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_idempotency_deduplication():
    """Verify that calling execute_action twice on identical item skips re-execution."""
    batch_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())

    # Pre-create batch and action item in DB
    async with async_session_factory() as session:
        batch = BatchModel(id=batch_id, raw_text="Sample text", status="executing")
        session.add(batch)
        item = ActionItemModel(
            id=item_id,
            batch_id=batch_id,
            description="Create Security Bug",
            suggested_tool="jira",
            source_snippet="Sample",
            confidence=0.9,
            status="pending",
        )
        session.add(item)
        await session.commit()

    payload = {
        "project_key": "FIN",
        "summary": "Fix invoice calculation edge case",
        "issue_type": "Bug",
    }

    # 1. First execution
    res1 = await mcp_client_manager.execute_action(
        batch_id=batch_id,
        item_id=item_id,
        tool="jira",
        payload=payload,
        item_description="Fix invoice calculation edge case",
        sandbox_mode=True,
    )
    assert res1.status == "success"
    assert "FIN-" in res1.external_url

    # Check DB state
    async with async_session_factory() as session:
        item_res = await session.execute(select(ActionItemModel).where(ActionItemModel.id == item_id))
        item_db = item_res.scalar_one()
        assert item_db.status == "executed"
        assert item_db.external_url == res1.external_url

        logs_res = await session.execute(select(ExecutionLogModel).where(ExecutionLogModel.item_id == item_id))
        logs = logs_res.scalars().all()
        assert len(logs) == 1

    # 2. Second execution with identical parameters (simulating Temporal retry)
    res2 = await mcp_client_manager.execute_action(
        batch_id=batch_id,
        item_id=item_id,
        tool="jira",
        payload=payload,
        item_description="Fix invoice calculation edge case",
        sandbox_mode=True,
    )
    assert res2.status == "success"
    assert res2.external_url == res1.external_url
    assert res2.raw_response.get("deduplicated") is True

    # Check DB still has only 1 log
    async with async_session_factory() as session:
        logs_res = await session.execute(select(ExecutionLogModel).where(ExecutionLogModel.item_id == item_id))
        logs = logs_res.scalars().all()
        assert len(logs) == 1  # No duplicate record created!

        # Cleanup
        b = (await session.execute(select(BatchModel).where(BatchModel.id == batch_id))).scalar_one_or_none()
        if b:
            await session.delete(b)
            await session.commit()


@pytest.mark.asyncio
async def test_invalid_tool_error_handling():
    with pytest.raises(ValueError) as exc:
        mcp_client_manager.get_connector("invalid_tool_xyz")
    assert "Unsupported tool" in str(exc.value)


@pytest.mark.asyncio
async def test_connectors_status_overview():
    status = await mcp_client_manager.get_connectors_status()
    assert "task_ledger" in status
    assert "notion" in status
    assert "jira" in status
    assert "calendar" in status
    assert status["task_ledger"]["healthy"] is True
