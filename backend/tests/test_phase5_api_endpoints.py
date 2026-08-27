"""Phase 5 Battle Test Suite: FastAPI REST API & Security Vault."""
import pytest
import uuid
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
from app.db.session import init_db, async_session_factory
from app.db.models import BatchModel, ActionItemModel, OAuthTokenModel
from app.core.security import encrypt_token, decrypt_token
from app.temporal.workflows import ProcessBatchWorkflow
from app.temporal.worker import create_worker, get_temporal_client


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


# ---------------------------------------------------------
# Test 1: Health & Security Vault Tests
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_api_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "sandbox_mode" in data


@pytest.mark.asyncio
async def test_oauth_vault_encryption():
    secret_token = "jira_pat_sec_987654321_topsecret"
    enc = encrypt_token(secret_token)
    assert enc != secret_token
    assert len(enc) > len(secret_token)

    dec = decrypt_token(enc)
    assert dec == secret_token


@pytest.mark.asyncio
async def test_connectors_endpoints_and_oauth_save():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Save OAuth token
        res = await client.post(
            "/api/connectors/oauth/save",
            json={
                "provider": "notion",
                "access_token": "secret_notion_oauth_token_123",
                "scopes": "pages:write,databases:read",
            },
        )
        assert res.status_code == 200

        # Verify DB storage is encrypted
        async with async_session_factory() as session:
            t = (await session.execute(select(OAuthTokenModel).where(OAuthTokenModel.provider == "notion"))).scalar_one()
            assert t.access_token_enc != "secret_notion_oauth_token_123"
            assert decrypt_token(t.access_token_enc) == "secret_notion_oauth_token_123"

        # 2. Get connectors status
        status_res = await client.get("/api/connectors/status")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["connectors"]["notion"]["oauth_connected"] is True
        assert data["connectors"]["task_ledger"]["healthy"] is True

        # 3. Toggle sandbox mode
        toggle_res = await client.post("/api/connectors/sandbox-toggle", json={"sandbox_mode": True})
        assert toggle_res.status_code == 200
        assert toggle_res.json()["sandbox_mode"] is True


# ---------------------------------------------------------
# Test 2: Full Ingest -> Review -> Approve -> History Lifecycle
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_full_api_batch_lifecycle():
    """Verify complete API flow: Ingest -> Poll Status -> Approve -> Check History."""
    # Start Temporal Worker in background
    temp_client = await get_temporal_client()
    worker = create_worker(temp_client)
    worker_task = asyncio.create_task(worker.run())

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Ingest Batch
            transcript = (
                "Sarah: Alex, please file a ticket for the checkout crash bug.\n"
                "Alex: I will schedule a review meeting with the team on Friday.\n"
            )
            ingest_res = await client.post(
                "/api/batches/ingest",
                json={
                    "raw_text": transcript,
                    "source_type": "meeting_transcript",
                },
            )
            assert ingest_res.status_code == 201
            ingest_data = ingest_res.json()
            batch_id = ingest_data["batch_id"]
            assert batch_id is not None

            # 2. Poll GET /api/batches/{id} until awaiting_approval
            items = []
            for _ in range(30):
                await asyncio.sleep(0.5)
                get_res = await client.get(f"/api/batches/{batch_id}")
                assert get_res.status_code == 200
                batch_data = get_res.json()
                if batch_data["status"] == "awaiting_approval" and len(batch_data["items"]) >= 2:
                    items = batch_data["items"]
                    break

            assert len(items) >= 2, "Items should be available for review"

            # 3. Submit Approval via POST /api/batches/{id}/approve
            decisions = [
                {
                    "item_id": items[0]["id"],
                    "action": "APPROVE",
                },
                {
                    "item_id": items[1]["id"],
                    "action": "APPROVE",
                },
            ]
            approve_res = await client.post(
                f"/api/batches/{batch_id}/approve",
                json={
                    "batch_id": batch_id,
                    "decisions": decisions,
                },
            )
            assert approve_res.status_code == 200
            assert approve_res.json()["status"] == "executing"

            # 4. Wait for execution completion
            for _ in range(30):
                await asyncio.sleep(0.5)
                get_res = await client.get(f"/api/batches/{batch_id}")
                if get_res.json()["status"] == "completed":
                    break

            final_data = (await client.get(f"/api/batches/{batch_id}")).json()
            assert final_data["status"] == "completed"

            # 5. Verify GET /api/history returns record with links
            hist_res = await client.get("/api/history")
            assert hist_res.status_code == 200
            history_list = hist_res.json()
            assert any(h["batch_id"] == batch_id for h in history_list)

            target_hist = next(h for h in history_list if h["batch_id"] == batch_id)
            assert target_hist["executed_items"] >= 2
            assert len(target_hist["logs"]) >= 2
            assert target_hist["logs"][0]["external_url"] is not None

    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------
# Test 3: Input Validation & 404 Error Handling
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_api_validation_errors():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Too short text (< 10 chars)
        res = await client.post(
            "/api/batches/ingest",
            json={"raw_text": "Hi", "source_type": "meeting_transcript"},
        )
        assert res.status_code == 422

        # Non-existent batch ID
        res_404 = await client.get(f"/api/batches/{uuid.uuid4()}")
        assert res_404.status_code == 404
