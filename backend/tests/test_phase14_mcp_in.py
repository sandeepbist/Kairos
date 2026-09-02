"""MCP-in battle tests: the Kairos pipeline exposed as MCP tools."""
import asyncio

import pytest

from app.mcp.servers.kairos import server as kairos_server

TEST_KEY = "mcp-e2e-key-abcdef123456"


def _set_key(monkeypatch, value=TEST_KEY):
    monkeypatch.setattr("app.config.settings.API_KEY", value)


async def _call(tool: str, args: dict):
    """Dispatches through the server's call_tool — the same path an
    external MCP host exercises."""
    result = await kairos_server.call_tool(tool, args)
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    import json

    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except (ValueError, TypeError):
                continue
    return {}


@pytest.mark.asyncio
async def test_mcp_tools_registered():
    tools = await kairos_server.list_tools()
    names = {t.name for t in tools}
    assert names == {"submit_transcript", "list_pending_items", "approve_items"}


@pytest.mark.asyncio
async def test_mcp_auth_gate(monkeypatch):
    """Every tool refuses the wrong operator key."""
    import os
    _set_key(monkeypatch)
    os.environ["API_KEY"] = TEST_KEY
    with pytest.raises(Exception):
        await kairos_server.call_tool(
            "list_pending_items", {"api_key": "wrong-key", "batch_id": "x"}
        )


@pytest.mark.asyncio
async def test_mcp_invalid_action_rejected_before_workflow(monkeypatch):
    """approve_items validates the decision shape locally — bad actions
    never reach the workflow."""
    _set_key(monkeypatch)
    with pytest.raises(Exception):
        await _call("approve_items", {
            "api_key": TEST_KEY,
            "batch_id": "x",
            "decisions": [{"item_id": "a", "action": "EXPLODE"}],
        })


@pytest.mark.asyncio
async def test_mcp_full_lifecycle(monkeypatch):
    """submit_transcript -> list_pending_items -> approve_items ->
    executed results, entirely over MCP tool dispatch."""
    from app.temporal.worker import create_worker, get_temporal_client
    from app.db.session import async_session_factory
    from app.db.models import BatchModel
    from sqlalchemy import select, delete as _delete

    _set_key(monkeypatch)

    # Clean slate for the batches this test creates
    async with async_session_factory() as s:
        await s.execute(_delete(BatchModel).where(BatchModel.id == "mcp-e2e-batch"))
        await s.commit()

    from app.mcp.client_manager import mcp_client_manager

    # Executions must run sandboxed in tests (no external credentials).
    original = mcp_client_manager.execute_action

    async def sandboxed_execute(batch_id, item_id, tool, payload, item_description=None, sandbox_mode=None):
        return await original(batch_id, item_id, tool, payload,
                              item_description=item_description, sandbox_mode=True)

    mcp_client_manager.execute_action = sandboxed_execute
    client = await get_temporal_client()
    worker = create_worker(client)
    worker_task = asyncio.create_task(worker.run())
    try:
        # 1. Submit a transcript over MCP
        submit = await _call("submit_transcript", {
            "api_key": TEST_KEY,
            "raw_text": (
                "Sarah: Alex, please file a ticket for the MCP gateway bug by Friday.\n"
                "Alex: I will schedule the integration review meeting on Thursday at 3 PM.\n"
                "John: Let me update the MCP spec doc in the roadmap wiki."
            ),
            "source_type": "meeting_transcript",
        })
        assert "batch_id" in submit
        batch_id = submit["batch_id"]

        # 2. Poll items over MCP until extraction completes
        data = None
        for _ in range(40):
            await asyncio.sleep(0.5)
            data = await _call("list_pending_items", {
                "api_key": TEST_KEY, "batch_id": batch_id,
            })
            if data["batch_status"] == "awaiting_approval" and len(data["items"]) >= 3:
                break
        assert data["batch_status"] == "awaiting_approval"
        items = data["items"]
        assert all(i["source_snippet"] for i in items)  # verbatim quotes present

        # 3. Approve over MCP — one rejected, rest approved
        decisions = []
        for i in items:
            if i["suggested_tool"] == "notion":
                decisions.append({"item_id": i["item_id"], "action": "REJECT",
                                  "rejection_reason": "already documented"})
            else:
                decisions.append({"item_id": i["item_id"], "action": "APPROVE"})
        approve = await _call("approve_items", {
            "api_key": TEST_KEY, "batch_id": batch_id, "decisions": decisions,
        })
        assert approve["accepted"] is True

        # 4. Poll to completion; executed items carry external URLs
        for _ in range(30):
            await asyncio.sleep(0.5)
            final = await _call("list_pending_items", {
                "api_key": TEST_KEY, "batch_id": batch_id,
            })
            if final["batch_status"] == "completed":
                break
        assert final["batch_status"] == "completed"
        executed = [i for i in final["items"] if i["status"] == "executed"]
        rejected = [i for i in final["items"] if i["status"] == "rejected"]
        assert len(executed) >= 2
        assert all(i["external_url"] for i in executed)
        assert len(rejected) == 1

        # 5. Forged approval over MCP: the workflow validator refuses
        forged_ok = False
        try:
            await _call("approve_items", {
                "api_key": TEST_KEY, "batch_id": batch_id,
                "decisions": [{"item_id": "totally-fake", "action": "APPROVE"}],
            })
        except Exception:
            forged_ok = True
        assert forged_ok, "validator must reject unknown-item approvals via MCP too"
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        mcp_client_manager.execute_action = original
        async with async_session_factory() as s:
            b = (await s.execute(select(BatchModel).where(BatchModel.id == batch_id))).scalar_one_or_none()
            if b:
                await s.delete(b)
                await s.commit()
