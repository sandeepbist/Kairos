"""Kairos MCP server: the pipeline itself as MCP tools.

Turns Kairos into a component of any MCP host's stack (Claude Desktop,
Cursor, custom agents): a host can submit a transcript, poll the
extracted items, and submit approval decisions — the same human-approved
execution the dashboard drives, available programmatically. Like the Task
Ledger, this is a real MCP server: tools dispatch through ``call_tool``,
and the server runs standalone over stdio.

Auth posture: single-operator. The server is intended for the same
operator's MCP host; it enforces the shared ``API_KEY`` by requiring the
caller to pass it as the ``api_key`` argument of every tool — MCP hosts
store this like any other server credential. Batch-level integrity is
inherited from the workflow's update validator (unknown item ids are
rejected before history).

Run standalone (stdio MCP server):
    python -m app.mcp.servers.kairos
"""
from typing import Any

from mcp.server.mcpserver import MCPServer

from app.config import settings

server = MCPServer(
    name="kairos",
    version="1.0.0",
    description=(
        "Ambient action engine: submit transcripts, retrieve extracted "
        "action items with verbatim source quotes, and approve them for "
        "execution into Notion, Jira, Calendar, Linear, Todoist, email "
        "drafts, or the Task Ledger. Nothing executes without approval."
    ),
)


def _check_key(api_key: str) -> None:
    """Single-operator gate: MCP callers must present the shared key."""
    if settings.API_KEY and api_key != settings.API_KEY:
        raise ValueError("Invalid api_key. Configure the Kairos operator key in your MCP host.")


@server.tool(
    name="submit_transcript",
    description="Submit an unstructured conversation (transcript, email thread, chat log) for action-item extraction. Returns the batch_id immediately; poll with list_pending_items.",
)
async def submit_transcript(
    api_key: str,
    raw_text: str,
    source_type: str = "meeting_transcript",
) -> dict[str, Any]:
    """Starts the standard extraction workflow for a new batch."""
    from app.api.endpoints.batches import create_and_start_batch
    from app.db.session import async_session_factory

    _check_key(api_key)
    async with async_session_factory() as session:
        result = await create_and_start_batch(raw_text, source_type, session)
    return {
        "batch_id": result["batch_id"],
        "status": result["status"],
        "note": "Extraction is asynchronous; poll list_pending_items until status is awaiting_approval.",
    }


@server.tool(
    name="list_pending_items",
    description="Retrieve a batch's status and extracted action items, each with its verbatim source snippet, suggested tool, confidence, and item_id (needed for approvals).",
)
async def list_pending_items(api_key: str, batch_id: str) -> dict[str, Any]:
    """Returns the review-ready items for one batch."""
    from sqlalchemy import select

    from app.db.models import ActionItemModel, BatchModel
    from app.db.session import async_session_factory

    _check_key(api_key)
    async with async_session_factory() as session:
        batch = (
            await session.execute(select(BatchModel).where(BatchModel.id == batch_id))
        ).scalar_one_or_none()
        if not batch:
            raise ValueError(f"Batch '{batch_id}' not found.")
        items = (
            await session.execute(
                select(ActionItemModel).where(ActionItemModel.batch_id == batch_id)
            )
        ).scalars().all()

    return {
        "batch_id": batch_id,
        "batch_status": batch.status,
        "token_count": batch.token_count,
        "items": [
            {
                "item_id": i.id,
                "description": i.description,
                "suggested_tool": i.suggested_tool,
                "source_snippet": i.source_snippet,
                "speaker": i.speaker,
                "suggested_assignee": i.suggested_assignee,
                "priority": i.priority,
                "confidence": i.confidence,
                "status": i.status,
                "external_url": i.external_url,
            }
            for i in items
        ],
    }


@server.tool(
    name="approve_items",
    description="Submit human approval decisions for a batch's items. Each decision needs the item_id (from list_pending_items) and an action: APPROVE, MODIFY_AND_APPROVE (with override_tool/modified_payload), or REJECT. The operator is the approver; this tool transmits their decision to the durable workflow, which validates every item_id.",
)
async def approve_items(
    api_key: str,
    batch_id: str,
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Sends decisions to the workflow via the validated update path.

    The workflow's ApprovalReceived validator rejects any payload with
    item ids outside the batch — before the decision enters history —
    and the caller receives that rejection synchronously.
    """
    from app.temporal.worker import get_temporal_client
    from app.temporal.workflows import ProcessBatchWorkflow

    _check_key(api_key)
    if not decisions:
        raise ValueError("At least one decision is required.")
    for d in decisions:
        if d.get("action") not in ("APPROVE", "MODIFY_AND_APPROVE", "REJECT"):
            raise ValueError(f"Invalid action '{d.get('action')}'.")
        if not d.get("item_id"):
            raise ValueError("Every decision needs an item_id.")

    client = await get_temporal_client()
    handle = client.get_workflow_handle(f"batch-wf-{batch_id}")
    result = await handle.execute_update(ProcessBatchWorkflow.ApprovalReceived, decisions)
    return {
        "accepted": result["accepted"],
        "decisions": result["decisions"],
        "note": "Batch is executing; poll list_pending_items for item results.",
    }


if __name__ == "__main__":
    import asyncio

    from mcp.server.stdio import stdio_server

    async def run_stdio() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run_stdio())
