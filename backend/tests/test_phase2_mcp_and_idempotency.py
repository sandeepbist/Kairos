"""Phase 2 Battle Test Suite: Custom Task Ledger MCP Server & MCP Client Manager."""
import pytest
import uuid
from sqlalchemy import select
from app.db.session import init_db, async_session_factory
from app.db.models import BatchModel, ActionItemModel, ExecutionLogModel
from app.mcp.servers.task_ledger import (
    server as task_ledger_server,
    create_task,
    list_tasks,
    complete_task,
    delete_task,
)
from app.mcp.client_manager import mcp_client_manager


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
# Test 1b: MCP protocol dispatch (server.call_tool path)
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_task_ledger_mcp_server_call_tool_dispatch():
    """Tools must be invocable through the MCP server tool layer, not just as functions."""
    # 1. Discover tools the way an MCP client would
    tools = await task_ledger_server.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == {"create_task", "list_tasks", "complete_task", "delete_task"}

    # 2. Dispatch create through the MCP protocol layer
    result = await task_ledger_server.call_tool(
        "create_task",
        {"title": "MCP protocol dispatch test", "priority": "high"},
    )
    structured = getattr(result, "structured_content", None) or {}
    content_text = getattr(result, "content", [{}])[0]
    import json
    payload = structured or json.loads(getattr(content_text, "text", "{}"))
    assert payload["status"] == "open"
    assert payload["title"] == "MCP protocol dispatch test"
    assert "task_ledger://tasks/" in payload["external_url"]
    task_id = payload["id"]

    # 3. Unknown tool must be rejected by the dispatch layer
    with pytest.raises(Exception):
        await task_ledger_server.call_tool("nonexistent_tool", {})

    # 4. Clean up
    await delete_task(task_id)


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


# ---------------------------------------------------------
# Test 4: New sinks — Linear, Todoist, Email draft
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_linear_connector_sandbox():
    connector = mcp_client_manager.get_connector("linear")
    result = await connector.execute(
        {"title": "Fix the onboarding funnel", "priority": "high"},
        sandbox_mode=True,
    )
    assert result.status == "success"
    assert result.tool == "linear"
    assert "linear.app" in result.external_url


@pytest.mark.asyncio
async def test_todoist_connector_sandbox():
    connector = mcp_client_manager.get_connector("todoist")
    result = await connector.execute(
        {"content": "Buy a new keyboard", "due_date": "next Friday"},
        sandbox_mode=True,
    )
    assert result.status == "success"
    assert "todoist.com" in result.external_url


@pytest.mark.asyncio
async def test_email_draft_connector_sandbox():
    connector = mcp_client_manager.get_connector("email_draft")
    result = await connector.execute(
        {"subject": "Contract renewal", "body": "Hi there", "to": "ops@company.com"},
        sandbox_mode=True,
    )
    assert result.status == "success"
    assert "mail.google.com" in (result.external_url or "")


@pytest.mark.asyncio
async def test_new_tool_keyword_routing():
    """Extractor routes Linear/Todoist/email-draft intent correctly."""
    from app.pipelines.extract import deterministic_fallback_extractor as dfe

    items = dfe("Priya: Please file the onboarding bug as a Linear issue.", "meeting_transcript")
    assert any(i["suggested_tool"] == "linear" for i in items)

    items2 = dfe("Raj: Add the grocery run to my Todoist today.", "general_notes")
    assert any(i["suggested_tool"] == "todoist" for i in items2)

    items3 = dfe("Maya: Please draft an email to the vendor about the renewal.", "meeting_transcript")
    assert any(i["suggested_tool"] == "email_draft" for i in items3)


@pytest.mark.asyncio
async def test_email_draft_reuses_gmail_vault_alias():
    """The connectors status maps email_draft's connection to the gmail
    vault provider."""
    from starlette.testclient import TestClient
    from app.main import app
    from app.db.session import async_session_factory as factory
    from app.db.models import OAuthTokenModel
    from app.core.security import encrypt_token
    import uuid as _uuid

    async with factory() as session:
        session.add(OAuthTokenModel(
            id=str(_uuid.uuid4()), provider="gmail",
            access_token_enc=encrypt_token("ya29.dummy-gmail-token-1234"),
        ))
        await session.commit()

    with TestClient(app) as client:
        res = client.get("/api/connectors/status")
        data = res.json()
        assert data["connectors"]["email_draft"]["oauth_connected"] is True

    async with factory() as session:
        from sqlalchemy import delete as _delete

        await session.execute(_delete(OAuthTokenModel).where(OAuthTokenModel.provider == "gmail"))
        await session.commit()


@pytest.mark.asyncio
async def test_action_item_schema_accepts_new_tools():
    """Regression: ActionItem (the GET /batches response schema) must
    accept every TargetTool — a persisted 'linear' final_tool once 500'd
    every read of the batch because the response literal was stale."""
    from app.schemas.action_item import ActionItem
    from datetime import datetime, timezone

    for tool in (
        "notion", "jira", "calendar", "task_ledger", "linear", "todoist",
        "email_draft", "github", "confluence_page", "google_tasks",
    ):
        item = ActionItem(
            id="x", batch_id="b", description="d", suggested_tool="task_ledger",
            final_tool=tool, tool_payload={}, source_snippet="s",
            confidence=0.9, created_at=datetime.now(timezone.utc),
        )
        assert item.final_tool == tool


# ---------------------------------------------------------
# Test 5: MCP remote transport — fallback semantics
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_transport_noop_without_endpoint_or_token():
    """execute_via_mcp returns None (REST fallback) when there is no
    endpoint mapping for the tool or no access token — never raises."""
    from app.mcp.connectors.mcp_transport import execute_via_mcp

    assert await execute_via_mcp("task_ledger", "token", {}) is None
    assert await execute_via_mcp("notion", "", {}) is None


@pytest.mark.asyncio
async def test_mcp_transport_unreachable_falls_back_cleanly():
    """A live connection failure to the remote server returns None —
    the REST connector path must remain fully usable."""
    from app.mcp.connectors.mcp_transport import execute_via_mcp, MCP_REMOTE_ENDPOINTS

    MCP_REMOTE_ENDPOINTS["notion"] = "https://mcp.notion.invalid/mcp"
    try:
        result = await execute_via_mcp("notion", "ya29.some-oauth-token", {"title": "x"})
        assert result is None
    finally:
        MCP_REMOTE_ENDPOINTS["notion"] = "https://mcp.notion.com/mcp"


def test_mcp_argument_mapping():
    """Kairos payloads map to remote MCP tool arguments with the right
    field normalizations."""
    from app.mcp.connectors.mcp_transport import _mcp_arguments

    notion_args = _mcp_arguments("notion", {"summary": "Roadmap doc", "details": "the body"})
    assert notion_args["title"] == "Roadmap doc" and notion_args["content"] == "the body"

    jira_args = _mcp_arguments("jira", {"summary": "Fix the bug", "issue_type": "Bug"})
    assert jira_args["summary"] == "Fix the bug"
    assert jira_args["issue_type"] == "Bug"
    assert jira_args["project_key"] == "PROJ"


@pytest.mark.asyncio
async def test_mcp_mocked_dispatch_success():
    """With a working (mocked) session, a structured MCP result is
    returned and consumed by the connector — no REST call needed."""
    from unittest.mock import AsyncMock, patch
    from app.mcp.connectors.mcp_transport import execute_via_mcp

    class FakeResult:
        is_error = False
        structured_content = {"id": "page-123", "url": "https://notion.so/page-123"}

    fake_session = AsyncMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)
    fake_session.call_tool = AsyncMock(return_value=FakeResult())

    with patch("mcp.client.streamable_http.streamable_http_client") as fake_transport, \
         patch("mcp.ClientSession", return_value=fake_session):
        fake_ctx = AsyncMock()
        fake_ctx.__aenter__ = AsyncMock(return_value=(None, None, None))
        fake_ctx.__aexit__ = AsyncMock(return_value=False)
        fake_transport.return_value = fake_ctx

        result = await execute_via_mcp("notion", "ya29.token", {"title": "hello"})
        assert result is not None
        assert result["url"] == "https://notion.so/page-123"
        fake_session.call_tool.assert_awaited_once()


# ---------------------------------------------------------
def _runtime_fixture() -> str:
    """Runtime-built placeholder; no credential literal in source."""
    import uuid as _u
    return "fixture-" + _u.uuid4().hex


# Test 6: Tier-2 sinks — GitHub, Confluence, Google Tasks
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_github_connector_sandbox():
    connector = mcp_client_manager.get_connector("github")
    result = await connector.execute(
        {"title": "Flaky payment retry test", "repo": "acme/planning"},
        sandbox_mode=True,
    )
    assert result.status == "success"
    assert result.tool == "github"
    assert "github.com/acme/planning/issues/" in result.external_url


def test_github_repo_spec_parsing():
    from app.mcp.connectors.github_connector import _parse_repo

    assert _parse_repo("acme/planning") == ("acme", "planning")
    assert _parse_repo("https://github.com/acme/planning") == ("acme", "planning")
    assert _parse_repo("https://github.com/acme/planning/") == ("acme", "planning")
    assert _parse_repo("acme") == (None, None)
    assert _parse_repo(None) == (None, None)


@pytest.mark.asyncio
async def test_github_connector_requires_repo():
    """Live path without a repo fails with a clear message (never a crash)."""
    connector = mcp_client_manager.get_connector("github")
    result = await connector.execute({"title": "No repo given"})
    assert result.status == "failed"
    assert "repository" in (result.error or "")


@pytest.mark.asyncio
async def test_confluence_connector_sandbox():
    connector = mcp_client_manager.get_connector("confluence_page")
    result = await connector.execute(
        {"title": "Decision log — billing migration", "space_key": "TEAM"},
        sandbox_mode=True,
    )
    assert result.status == "success"
    assert "atlassian.com/wiki/spaces/TEAM" in result.external_url


@pytest.mark.asyncio
async def test_confluence_connector_requires_space():
    connector = mcp_client_manager.get_connector("confluence_page")
    result = await connector.execute({"title": "No space given"})
    assert result.status == "failed"
    assert "space" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_google_tasks_connector_sandbox():
    connector = mcp_client_manager.get_connector("google_tasks")
    result = await connector.execute(
        {"title": "Pick up visa documents", "due_date": "2026-09-10"},
        sandbox_mode=True,
    )
    assert result.status == "success"
    assert "tasks.google.com" in result.external_url


@pytest.mark.asyncio
async def test_new_tier2_tool_keyword_routing():
    """Extractor routes GitHub/Confluence/Google-Tasks intent correctly."""
    from app.pipelines.extract import deterministic_fallback_extractor as dfe

    items = dfe(
        "Lead: Dev, open a GitHub issue for the flaky payment retry test in the repo.",
        "meeting_transcript",
    )
    assert any(i["suggested_tool"] == "github" for i in items)
    assert any(i.get("suggested_assignee") == "Dev" for i in items if i["suggested_tool"] == "github")

    items2 = dfe(
        "Sarah: We should write the decision log up as a Confluence page after this call.",
        "meeting_transcript",
    )
    assert any(i["suggested_tool"] == "confluence_page" for i in items2)

    items3 = dfe(
        "Maya: Add picking up the visa documents to my Google Tasks.",
        "meeting_transcript",
    )
    assert any(i["suggested_tool"] == "google_tasks" for i in items3)


@pytest.mark.asyncio
async def test_confluence_alias_rides_jira_credential():
    """The connectors status maps confluence_page's connection to the
    jira vault provider (same Atlassian credential). Vault rows are
    created and removed through the public API surface."""
    from starlette.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        client.delete("/api/connectors/oauth/jira")
        res = client.post(
            "/api/connectors/oauth/save",
            json={
                "provider": "jira",
                "access_token": _runtime_fixture(),
            },
        )
        assert res.status_code == 200

        status = client.get("/api/connectors/status").json()
        assert status["connectors"]["confluence_page"]["oauth_connected"] is True

        client.delete("/api/connectors/oauth/jira")
        status_after = client.get("/api/connectors/status").json()
        assert status_after["connectors"]["confluence_page"]["oauth_connected"] is False


@pytest.mark.asyncio
async def test_github_labels_accept_string_or_list():
    """The review UI edits labels as a comma string; the connector
    normalizes both forms before the API call."""
    captured = {}

    class FakeResp:
        is_success = True
        status_code = 201

        def json(self):
            return {"id": 1, "number": 7, "html_url": "https://github.com/a/b/issues/7"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, json=None, headers=None):
            captured.update(json or {})
            return FakeResp()

    import app.mcp.connectors.github_connector as gc

    orig = gc.connector_http_client
    gc.connector_http_client = lambda timeout=15.0: FakeClient()
    orig_token = gc.GitHubConnector._get_token

    async def _seeded_token(self):
        return _runtime_fixture()

    gc.GitHubConnector._get_token = _seeded_token
    try:
        connector = gc.GitHubConnector()
        result = await connector.execute(
            {"title": "T", "repo": "a/b", "labels": "kairos, bug"},
        )
        assert result.status == "success", result.error
        assert captured["labels"] == ["kairos", "bug"]
    finally:
        gc.connector_http_client = orig
        gc.GitHubConnector._get_token = orig_token
