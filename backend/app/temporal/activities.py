"""Temporal Activities for Kairos Batch Processing Pipeline."""
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError
from sqlalchemy import select
from app.db.session import async_session_factory
from app.db.models import BatchModel, ActionItemModel
from app.pipelines.graph import run_extraction_pipeline
from app.pipelines.memory import routing_memory
from app.mcp.client_manager import mcp_client_manager


@activity.defn
async def extract_and_route_activity(
    batch_id: str,
    raw_text: str,
    source_type: str,
) -> dict[str, Any]:
    """Runs LangGraph stateless extraction and routing pipeline."""
    state = await run_extraction_pipeline(
        batch_id=batch_id,
        raw_text=raw_text,
        source_type=source_type,
    )
    return {
        "routed_items": state["routed_items"],
        "token_count": state["token_count"],
        "warning_flags": state["warning_flags"],
        "errors": state["errors"],
    }


@activity.defn
async def persist_extracted_items_activity(
    batch_id: str,
    routed_items: list[dict[str, Any]],
    token_count: int,
) -> list[str]:
    """Persists extracted candidates to PostgreSQL and sets batch status to awaiting_approval."""
    item_ids = []
    async with async_session_factory() as session:
        # Update batch
        batch_query = select(BatchModel).where(BatchModel.id == batch_id)
        batch_res = await session.execute(batch_query)
        batch = batch_res.scalar_one_or_none()
        if not batch:
            # Batch was erased (operator deletion) while the workflow ran.
            # Retrying cannot succeed — fail this activity permanently and
            # let the workflow's remaining steps become no-ops.
            raise ApplicationError(
                f"Batch {batch_id} no longer exists (erased during processing); abandoning.",
                non_retryable=True,
            )
        batch.status = "awaiting_approval"
        batch.token_count = token_count
        from app.pipelines.events import record_event

        await record_event(
            batch_id, "awaiting_review",
            f"{len(routed_items)} items ready for review",
        )

        # Insert items
        for item in routed_items:
            item_id = item.get("id")
            item_model = ActionItemModel(
                id=item_id,
                batch_id=batch_id,
                description=item["description"],
                suggested_tool=item["suggested_tool"],
                final_tool=item["suggested_tool"],
                tool_payload=item.get("tool_payload", {}),
                source_snippet=item.get("source_snippet", item["description"]),
                speaker=item.get("speaker"),
                suggested_assignee=item.get("suggested_assignee"),
                actionability_type=item.get("actionability_type", "task"),
                priority=item.get("priority", "medium"),
                confidence=float(item.get("confidence", 0.8)),
                status="pending",
            )
            session.add(item_model)
            item_ids.append(item_id)

        await session.commit()
    return item_ids


@activity.defn
async def execute_approved_item_activity(
    batch_id: str,
    item_id: str,
    tool: str,
    payload: dict[str, Any],
    description: str,
    sandbox_mode: bool | None = None,
) -> dict[str, Any]:
    """Executes single approved action item via McpClientManager with SHA256 deduplication."""
    result = await mcp_client_manager.execute_action(
        batch_id=batch_id,
        item_id=item_id,
        tool=tool,
        payload=payload,
        item_description=description,
        sandbox_mode=sandbox_mode,
    )
    return {
        "status": result.status,
        "external_url": result.external_url,
        "latency_ms": result.latency_ms,
        "error": result.error,
        "raw_response": result.raw_response,
    }


@activity.defn
async def reject_item_activity(
    batch_id: str,
    item_id: str,
    rejection_reason: str | None,
) -> dict[str, Any]:
    """Marks an item as rejected in the database."""
    async with async_session_factory() as session:
        item_query = select(ActionItemModel).where(ActionItemModel.id == item_id)
        item_res = await session.execute(item_query)
        item = item_res.scalar_one_or_none()
        if item:
            item.status = "rejected"
            item.rejection_reason = rejection_reason or "Rejected by user during review"
            await session.commit()
            return {"status": "rejected", "item_id": item_id}
    return {"status": "not_found", "item_id": item_id}


@activity.defn
async def update_routing_memory_activity(
    item_id: str,
    batch_id: str,
    description: str,
    suggested_tool: str,
    final_tool: str,
    was_overridden: bool,
) -> None:
    """Records user confirmation or override in the semantic routing memory."""
    await routing_memory.record_feedback(
        item_id=item_id,
        batch_id=batch_id,
        item_description=description,
        suggested_tool=suggested_tool,
        final_tool=final_tool,
        was_overridden=was_overridden,
    )


@activity.defn
async def complete_batch_activity(batch_id: str) -> dict[str, Any]:
    """Marks batch status as completed in database."""
    async with async_session_factory() as session:
        batch_query = select(BatchModel).where(BatchModel.id == batch_id)
        batch_res = await session.execute(batch_query)
        batch = batch_res.scalar_one_or_none()
        if batch:
            batch.status = "completed"
            await session.commit()
            return {"batch_id": batch_id, "status": "completed"}
    return {"batch_id": batch_id, "status": "not_found"}


@activity.defn
async def expire_batch_activity(batch_id: str) -> dict[str, Any]:
    """Auto-archives batch after 7-day approval timeout."""
    async with async_session_factory() as session:
        batch_query = select(BatchModel).where(BatchModel.id == batch_id)
        batch_res = await session.execute(batch_query)
        batch = batch_res.scalar_one_or_none()
        if batch:
            batch.status = "expired"
            await session.commit()
            return {"batch_id": batch_id, "status": "expired"}
    return {"batch_id": batch_id, "status": "not_found"}
