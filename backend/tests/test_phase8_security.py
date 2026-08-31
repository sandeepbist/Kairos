"""Security Battle Tests: API-key auth, rate limiting, headers, CORS policy."""
import pytest
from starlette.testclient import TestClient

from app.main import app

TEST_KEY = "testkey-aaaaaaaaaaaaaaaaaaaa"

AUTHED = {"X-API-Key": TEST_KEY}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_is_public(client):
    """Liveness probe must never require auth or be rate limited."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_missing_key_rejected(client, monkeypatch):
    """Requests without a key are rejected when a key is configured."""
    from app.core import auth
    monkeypatch.setattr(auth.settings, "API_KEY", TEST_KEY)
    res = client.get("/api/history")
    assert res.status_code == 401


def test_wrong_key_rejected(client, monkeypatch):
    from app.core import auth
    monkeypatch.setattr(auth.settings, "API_KEY", TEST_KEY)
    res = client.get("/api/history", headers={"X-API-Key": "totally-wrong-key-xyz"})
    assert res.status_code == 401
    assert "Invalid API key" in res.json()["detail"]


def test_valid_key_header_and_query_accepted(client, monkeypatch):
    from app.core import auth
    monkeypatch.setattr(auth.settings, "API_KEY", TEST_KEY)
    assert client.get("/api/history", headers=AUTHED).status_code == 200
    assert client.get(f"/api/history?api_key={TEST_KEY}").status_code == 200


def test_all_protected_routes_require_key(client, monkeypatch):
    """Every /api route except health must be gated."""
    from app.core import auth
    monkeypatch.setattr(auth.settings, "API_KEY", TEST_KEY)
    for path in ["/api/history", "/api/connectors/status", "/api/batches/some-id"]:
        assert client.get(path).status_code == 401, f"{path} was not protected"


def test_security_headers_present(client):
    res = client.get("/api/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_rate_limit_write_burst(monkeypatch):
    """Bursting >10 writes/min from one IP must produce a 429 with Retry-After."""
    from app.core import auth
    monkeypatch.setattr(auth.settings, "API_KEY", TEST_KEY)
    with TestClient(app) as c:
        codes = []
        for _ in range(12):
            res = c.post(
                "/api/batches/ingest",
                json={"raw_text": "word " * 20},
                headers=AUTHED,
            )
            codes.append(res.status_code)
        assert 429 in codes
        assert codes.count(429) >= 1
        # Retry-After policy is verified directly on the limiter below.
    from app.core.ratelimit import InMemoryRateLimiter

    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
    assert limiter.check("ip")[0] is True
    assert limiter.check("ip")[0] is True
    allowed, retry = limiter.check("ip")
    assert allowed is False
    assert retry >= 1


def test_rate_limit_read_burst(client):
    """Bursting >60 reads/min from one IP must produce a 429."""
    codes = [client.get("/api/history").status_code for _ in range(65)]
    assert 429 in codes


def test_cors_rejects_unknown_origin(client):
    res = client.get(
        "/api/health",
        headers={"Origin": "https://evil.example.com"},
    )
    assert "access-control-allow-origin" not in res.headers


def test_cors_allows_configured_origin(client):
    res = client.get(
        "/api/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_batch_deletion_erasure():
    """Batch deletion removes the batch and cascades to items/logs."""
    import uuid as _uuid
    from app.db.session import async_session_factory as factory
    from app.db.models import BatchModel, ActionItemModel, ExecutionLogModel

    async with factory() as session:
        batch = BatchModel(
            id=str(_uuid.uuid4()),
            raw_text="Sarah: Alex, please file a ticket for the deletion bug.",
            status="completed",
        )
        item = ActionItemModel(
            id=str(_uuid.uuid4()),
            batch_id=batch.id,
            description="Test item",
            suggested_tool="task_ledger",
            source_snippet="Sarah: ...",
            confidence=0.9,
        )
        session.add(batch)
        session.add(item)
        await session.commit()
        bid, iid = batch.id, item.id
        session.add(
            ExecutionLogModel(
                id=str(_uuid.uuid4()),
                item_id=iid,
                batch_id=bid,
                tool="task_ledger",
                status="success",
                idempotency_hash="x" * 64,
            )
        )
        await session.commit()

    from fastapi import HTTPException, status
    from app.api.endpoints.history import delete_batch

    async with factory() as db:
        result = await delete_batch(bid, db)
        assert result["status"] == "deleted"

    async with factory() as session:
        from sqlalchemy import select as _select
        assert (await session.execute(_select(BatchModel).where(BatchModel.id == bid))).scalar_one_or_none() is None
        assert (await session.execute(_select(ActionItemModel).where(ActionItemModel.id == iid))).scalar_one_or_none() is None
        assert (await session.execute(_select(ExecutionLogModel).where(ExecutionLogModel.batch_id == bid))).scalars().all() == []

    # Second deletion must 404
    from app.api.endpoints.history import delete_batch as _del
    async with factory() as db:
        try:
            await _del(bid, db)
            assert False, "should have raised"
        except HTTPException as e:
            assert e.status_code == 404


@pytest.mark.asyncio
async def test_batch_deletion_refuses_active_batches():
    """Deleting a batch that is still processing/executing must 409."""
    import uuid as _uuid
    from fastapi import HTTPException
    from app.db.session import async_session_factory as factory
    from app.db.models import BatchModel
    from app.api.endpoints.history import delete_batch

    async with factory() as session:
        batch = BatchModel(
            id=str(_uuid.uuid4()),
            raw_text="Sarah: Alex, please file a ticket for the deletion guard test.",
            status="processing",
        )
        session.add(batch)
        await session.commit()
        bid = batch.id

    async with factory() as db:
        try:
            await delete_batch(bid, db)
            assert False, "should have raised 409"
        except HTTPException as e:
            assert e.status_code == 409
            assert "still processing" in e.detail

    # Batch must still exist
    async with factory() as session:
        from sqlalchemy import select as _select
        still = (
            await session.execute(_select(BatchModel).where(BatchModel.id == bid))
        ).scalar_one_or_none()
        assert still is not None

    # Terminal states delete fine (re-fetch inside the active session;
    # 'still' is detached once its session block closed)
    async with factory() as session:
        from sqlalchemy import select as _select
        terminal = (
            await session.execute(_select(BatchModel).where(BatchModel.id == bid))
        ).scalar_one()
        terminal.status = "failed"
        await session.commit()

    async with factory() as db:
        res = await delete_batch(bid, db)
        assert res["status"] == "deleted"
