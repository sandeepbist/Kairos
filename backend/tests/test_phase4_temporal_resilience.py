"""Phase 4 Battle Test Suite: Temporal Durable Orchestrator & Idempotency Worker."""
import pytest
import uuid
import asyncio

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
            args=[batch_id, batch.raw_text, "meeting_transcript", True],  # sandbox_mode=True
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

        # Submit approval as a workflow update; the validator runs first
        await handle.execute_update(
            ProcessBatchWorkflow.ApprovalReceived, decisions,
        )

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
            args=[batch_id, batch.raw_text, "slack_conversation", True],  # sandbox_mode=True
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

        await handle.execute_update(
            ProcessBatchWorkflow.ApprovalReceived, decisions,
        )
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


@pytest.mark.asyncio
async def test_forged_approval_rejected_by_validator():
    """Approval updates referencing unknown item ids are rejected by the
    platform validator — before the decision enters workflow history —
    and the batch keeps waiting for a legitimate approval."""
    from temporalio.client import Client as TClient
    from temporalio.worker import Worker as TWorker
    from app.temporal.activities import (
        extract_and_route_activity,
        persist_extracted_items_activity,
        execute_approved_item_activity,
        reject_item_activity,
        update_routing_memory_activity,
        complete_batch_activity,
        expire_batch_activity,
    )

    client = await TClient.connect(settings.TEMPORAL_HOST, namespace=settings.TEMPORAL_NAMESPACE)
    test_queue = f"test-queue-validator-{uuid.uuid4()}"
    worker = TWorker(
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
        workflow_id = f"batch-wf-validator-{batch_id}"
        async with async_session_factory() as session:
            session.add(BatchModel(
                id=batch_id,
                raw_text="Sarah: Alex, please file a ticket for the guard test.",
                status="processing",
                temporal_workflow_id=workflow_id,
            ))
            await session.commit()

        handle = await client.start_workflow(
            ProcessBatchWorkflow.run,
            args=[batch_id, "Sarah: Alex, please file a ticket for the guard test.", "meeting_transcript", True],
            id=workflow_id,
            task_queue=test_queue,
        )

        # Wait for extraction so known-item ids exist
        for _ in range(30):
            await asyncio.sleep(0.5)
            async with async_session_factory() as session:
                b = (await session.execute(select(BatchModel).where(BatchModel.id == batch_id))).scalar_one_or_none()
                if b and b.status == "awaiting_approval":
                    break

        # Forged payload: unknown item ids — the update must throw
        forged = [{"item_id": "not-in-batch", "action": "APPROVE"}]
        rejected = False
        try:
            await handle.execute_update(ProcessBatchWorkflow.ApprovalReceived, forged)
        except Exception:
            rejected = True
        assert rejected, "validator must reject unknown-item approvals"

        # Batch is still awaiting a real approval
        async with async_session_factory() as session:
            b = (await session.execute(select(BatchModel).where(BatchModel.id == batch_id))).scalar_one()
            assert b.status == "awaiting_approval"

        # The workflow still accepts the legitimate decision afterward
        async with async_session_factory() as session:
            items = (await session.execute(
                select(ActionItemModel).where(ActionItemModel.batch_id == batch_id)
            )).scalars().all()
        legit = [{"item_id": i.id, "action": "APPROVE"} for i in items]
        res = await handle.execute_update(ProcessBatchWorkflow.ApprovalReceived, legit)
        assert res["accepted"] is True
        final = await handle.result()
        assert final["status"] == "completed"
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
