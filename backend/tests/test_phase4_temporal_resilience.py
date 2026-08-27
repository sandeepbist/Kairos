"""Phase 4 Battle Test Suite: Temporal Durable Orchestrator & Idempotency Worker."""
import pytest
import uuid
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from temporalio.client import Client
from temporalio.worker import Worker
from app.config import settings
from app.db.session import init_db, async_session_factory
from app.db.models import BatchModel, ActionItemModel, ExecutionLogModel
from app.temporal.workflows import ProcessBatchWorkflow
from app.temporal.activities import (
    extract_and_route_activity,
    persist_extracted_items_activity,
    execute_approved_item_activity,
    reject_item_activity,
    update_routing_memory_activity,
    complete_batch_activity,
    expire_batch_activity,
)


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


# ---------------------------------------------------------
# Test 1: Full Temporal Workflow Lifecycle with Signal Wait
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_temporal_process_batch_workflow_end_to_end():
    """Verify durable workflow: Ingest -> LangGraph Activity -> Signal Wait -> MCP Execution."""
    client = await Client.connect(settings.TEMPORAL_HOST, namespace=settings.TEMPORAL_NAMESPACE)
    test_queue = f"test-queue-{uuid.uuid4()}"

    worker = Worker(
        client,
        task_queue=test_queue,
        workflows=[ProcessBatchWorkflow],
        activities=[
            extract_and_route_activity,
            persist_extracted_items_activity,
            execute_approved_item_activity,
            reject_item_activity,
            update_routing_memory_activity,
            complete_batch_activity,
            expire_batch_activity,
        ],
    )

    worker_task = asyncio.create_task(worker.run())

    try:
        batch_id = str(uuid.uuid4())
        workflow_id = f"batch-wf-{batch_id}"

        # Pre-create batch record in DB as FastAPI endpoint would
        async with async_session_factory() as session:
            batch = BatchModel(
                id=batch_id,
                source_type="meeting_transcript",
                raw_text=(
                    "Sarah: Alex, please file a ticket for the checkout crash bug.\n"
                    "Alex: I will schedule a review meeting on Friday.\n"
                    "John: Let me document the database migration guide.\n"
                ),
                status="processing",
                temporal_workflow_id=workflow_id,
            )
            session.add(batch)
            await session.commit()

        # Start Workflow
        handle = await client.start_workflow(
            ProcessBatchWorkflow.run,
            args=[batch_id, batch.raw_text, "meeting_transcript"],
            id=workflow_id,
            task_queue=test_queue,
        )

        # Wait until items are extracted and persisted to DB (awaiting_approval)
        for _ in range(30):
            await asyncio.sleep(0.5)
            async with async_session_factory() as session:
                b_res = await session.execute(select(BatchModel).where(BatchModel.id == batch_id))
                b = b_res.scalar_one_or_none()
                if b and b.status == "awaiting_approval":
                    break

        async with async_session_factory() as session:
            items_res = await session.execute(select(ActionItemModel).where(ActionItemModel.batch_id == batch_id))
            items = items_res.scalars().all()
            assert len(items) >= 2, "Items should be extracted and persisted in DB"

            item_map = {item.suggested_tool: item for item in items}

            # Build Human Approval Decisions
            decisions = []
            if "jira" in item_map:
                decisions.append({
                    "item_id": item_map["jira"].id,
                    "action": "APPROVE",
                })
            if "calendar" in item_map:
                decisions.append({
                    "item_id": item_map["calendar"].id,
                    "action": "MODIFY_AND_APPROVE",
                    "override_tool": "calendar",
                    "modified_payload": {
                        "title": "Modified Sprint Review Call",
                        "start_time": "2026-09-05T10:00:00Z",
                        "end_time": "2026-09-05T11:00:00Z",
                    },
                })
            if "notion" in item_map:
                decisions.append({
                    "item_id": item_map["notion"].id,
                    "action": "REJECT",
                    "rejection_reason": "Already documented in confluence",
                })

        # Send Temporal Signal
        await handle.signal(ProcessBatchWorkflow.ApprovalReceived, decisions)

        # Wait for Workflow Completion
        result = await handle.result()
        assert result["status"] == "completed"
        assert result["batch_id"] == batch_id

        # Verify DB Final States
        async with async_session_factory() as session:
            b_final = (await session.execute(select(BatchModel).where(BatchModel.id == batch_id))).scalar_one()
            assert b_final.status == "completed"

            logs_res = await session.execute(select(ExecutionLogModel).where(ExecutionLogModel.batch_id == batch_id))
            logs = logs_res.scalars().all()
            assert len(logs) >= 1
            for log in logs:
                assert log.status == "success"
                assert log.external_url is not None

    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------
# Test 2: Workflow Rejection Handling
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_temporal_process_batch_all_rejections():
    """Verify workflow handles 100% rejection decisions cleanly."""
    client = await Client.connect(settings.TEMPORAL_HOST, namespace=settings.TEMPORAL_NAMESPACE)
    test_queue = f"test-queue-{uuid.uuid4()}"

    worker = Worker(
        client,
        task_queue=test_queue,
        workflows=[ProcessBatchWorkflow],
        activities=[
            extract_and_route_activity,
            persist_extracted_items_activity,
            execute_approved_item_activity,
            reject_item_activity,
            update_routing_memory_activity,
            complete_batch_activity,
            expire_batch_activity,
        ],
    )

    worker_task = asyncio.create_task(worker.run())

    try:
        batch_id = str(uuid.uuid4())
        workflow_id = f"batch-wf-reject-{batch_id}"

        async with async_session_factory() as session:
            batch = BatchModel(
                id=batch_id,
                source_type="slack_conversation",
                raw_text="Mark: Can someone look into updating the header logo?",
                status="processing",
                temporal_workflow_id=workflow_id,
            )
            session.add(batch)
            await session.commit()

        handle = await client.start_workflow(
            ProcessBatchWorkflow.run,
            args=[batch_id, batch.raw_text, "slack_conversation"],
            id=workflow_id,
            task_queue=test_queue,
        )

        for _ in range(30):
            await asyncio.sleep(0.5)
            async with async_session_factory() as session:
                b_res = await session.execute(select(BatchModel).where(BatchModel.id == batch_id))
                b = b_res.scalar_one_or_none()
                if b and b.status == "awaiting_approval":
                    break

        async with async_session_factory() as session:
            items = (await session.execute(select(ActionItemModel).where(ActionItemModel.batch_id == batch_id))).scalars().all()
            decisions = [
                {"item_id": item.id, "action": "REJECT", "rejection_reason": "Not prioritized"}
                for item in items
            ]

        await handle.signal(ProcessBatchWorkflow.ApprovalReceived, decisions)
        result = await handle.result()
        assert result["status"] == "completed"

        async with async_session_factory() as session:
            for item in items:
                refreshed = (await session.execute(select(ActionItemModel).where(ActionItemModel.id == item.id))).scalar_one()
                assert refreshed.status == "rejected"
                assert refreshed.rejection_reason == "Not prioritized"

    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
