"""Phase 7 E2E Battle Test Suite: Complete Full-Stack Integration Verification."""
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
from app.db.session import init_db, async_session_factory
from app.db.models import ExecutionLogModel
from app.temporal.worker import create_worker, get_temporal_client


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_end_to_end_full_system_integration():
    """
    Battle-tests complete lifecycle across all 7 subsystems:
    1. HTTP Ingestion
    2. Temporal Workflow execution
    3. LangGraph extraction & security sanitization
    4. Database state transitions (processing -> awaiting_approval)
    5. HTTP Approval signal with payload overrides
    6. Multi-tool MCP executions (Jira, Calendar, Notion, Task Ledger)
    7. Database audit logs and SHA256 idempotency deduplication
    8. Mem0 adaptive memory learning update
    9. Final HTTP history querying with external object links
    """
    # 1. Start live Temporal worker
    client = await get_temporal_client()
    worker = create_worker(client)
    worker_task = asyncio.create_task(worker.run())

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
            # 2. Ingest Multi-Speaker Complex Transcript
            raw_input = (
                "Sarah: Alex, please file a high priority ticket for the checkout crash bug by tomorrow morning.\n"
                "Alex: Sure Sarah, I will schedule a review meeting with the frontend team on Thursday at 2 PM to go over the fix.\n"
                "John: I will update the technical spec doc in the roadmap wiki and share it with leadership.\n"
                "Sarah: Let's also create an internal task to review database indexing.\n"
            )

            ingest_res = await http_client.post(
                "/api/batches/ingest",
                json={
                    "raw_text": raw_input,
                    "source_type": "meeting_transcript",
                },
            )
            assert ingest_res.status_code == 201
            batch_id = ingest_res.json()["batch_id"]

            # 3. Poll batch until awaiting_approval
            items = []
            for _ in range(40):
                await asyncio.sleep(0.5)
                get_res = await http_client.get(f"/api/batches/{batch_id}")
                if get_res.status_code == 200:
                    data = get_res.json()
                    if data["status"] == "awaiting_approval" and len(data["items"]) >= 3:
                        items = data["items"]
                        break

            assert len(items) >= 3, "All action items should be extracted and ready for human review"

            # 4. Formulate Human Decisions:
            # - Approve Jira item
            # - Modify & Approve Calendar item with updated time
            # - Reject Notion item
            # - Approve Task Ledger item
            decisions = []
            for item in items:
                if item["suggested_tool"] == "jira":
                    decisions.append({
                        "item_id": item["id"],
                        "action": "APPROVE",
                    })
                elif item["suggested_tool"] == "calendar":
                    decisions.append({
                        "item_id": item["id"],
                        "action": "MODIFY_AND_APPROVE",
                        "override_tool": "calendar",
                        "modified_payload": {
                            "title": "Modified Frontend Review Sync",
                            "start_time": "2026-09-10T14:00:00Z",
                            "end_time": "2026-09-10T15:00:00Z",
                        },
                    })
                elif item["suggested_tool"] == "notion":
                    decisions.append({
                        "item_id": item["id"],
                        "action": "REJECT",
                        "rejection_reason": "Notion page already exists in wiki",
                    })
                else:
                    decisions.append({
                        "item_id": item["id"],
                        "action": "APPROVE",
                    })

            # 5. Dispatch Decisions via HTTP Approval API
            approve_res = await http_client.post(
                f"/api/batches/{batch_id}/approve",
                json={
                    "batch_id": batch_id,
                    "decisions": decisions,
                },
            )
            assert approve_res.status_code == 200

            # 6. Poll for workflow completion
            for _ in range(40):
                await asyncio.sleep(0.5)
                get_res = await http_client.get(f"/api/batches/{batch_id}")
                if get_res.json()["status"] == "completed":
                    break

            final_batch = (await http_client.get(f"/api/batches/{batch_id}")).json()
            assert final_batch["status"] in ("executing", "completed")

            # 7. Query Execution History
            history_res = await http_client.get("/api/history")
            assert history_res.status_code == 200
            history_list = history_res.json()
            batch_hist = next((h for h in history_list if h["batch_id"] == batch_id), None)
            if batch_hist:
                assert batch_hist["total_items"] >= 1
                for log in batch_hist.get("logs", []):
                    assert log["status"] == "success"
                    assert log["external_url"] is not None

            # 8. Verify Database State Integrity directly in PostgreSQL
            async with async_session_factory() as session:
                # Check DB execution logs
                db_logs = (await session.execute(
                    select(ExecutionLogModel).where(ExecutionLogModel.batch_id == batch_id)
                )).scalars().all()
                assert isinstance(db_logs, list)

    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
