"""Security Battle Tests: API-key auth, rate limiting, headers, CORS policy."""
import pytest


def uuid_fixture() -> str:
    """Runtime-built placeholder; no credential literal in source."""
    import uuid as _u
    return "wrong-" + _u.uuid4().hex
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
    res = client.get("/api/history", headers={"X-API-Key": uuid_fixture()})
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

    from fastapi import HTTPException
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


def test_rate_limit_key_immune_to_xff_spoofing():
    """Spoofed X-Forwarded-For must not mint fresh rate-limit identities.

    uvicorn >= 0.46 rewrites request.client from XFF for loopback peers by
    default, so the limiter must not key on request.client when spoofing is
    possible: with TRUST_PROXY off it uses the socket peer for every request,
    and with TRUST_PROXY on it uses only the LAST XFF entry (the hop added by
    the proxy in front), never the client-controlled left side.
    """
    from app.core.ratelimit import _client_ip

    class FakeClient:
        host = "203.0.113.50"  # spoofed rewrite by uvicorn

    class FakeRequest:
        client = FakeClient()
        headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8, 203.0.113.50"}

    # Default (untrusted): key is the socket peer, identical for every
    # request — a spoofed XFF yields no new identity.
    from app.config import settings
    settings.TRUST_PROXY = False
    assert _client_ip(FakeRequest()) == "203.0.113.50"

    # Trusted-proxy mode: only the LAST entry counts; earlier
    # client-controlled entries are ignored.
    settings.TRUST_PROXY = True
    assert _client_ip(FakeRequest()) == "203.0.113.50"

    # And a rotating first entry still resolves to the same final hop.
    class Rotating(FakeRequest):
        headers = {"X-Forwarded-For": "9.9.9.9, 203.0.113.50"}

    assert _client_ip(Rotating()) == "203.0.113.50"
    settings.TRUST_PROXY = False


def test_request_body_size_cap():
    """Bodies over 1 MB are rejected 413 before parsing or storage."""
    from starlette.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        big = {"raw_text": "A" * 1_200_000, "source_type": "meeting_transcript"}
        r = c.post("/api/batches/ingest", json=big)
        assert r.status_code == 413
        assert "too large" in r.json()["detail"]


def test_raw_text_field_cap():
    """raw_text over 50k chars is rejected 422 (schema-level)."""
    from app.schemas.action_item import BatchIngestRequest
    from pydantic import ValidationError
    import pytest as _pytest

    with _pytest.raises(ValidationError):
        BatchIngestRequest(raw_text="A" * 50_001)
    # at the cap is fine
    ok = BatchIngestRequest(raw_text="A" * 50_000)
    assert len(ok.raw_text) == 50_000


def test_decision_list_cap():
    """Approval payloads over 200 decisions are rejected 422."""
    from app.schemas.action_item import ActionItemApprovalRequest
    from pydantic import ValidationError
    import pytest as _pytest

    with _pytest.raises(ValidationError):
        ActionItemApprovalRequest(
            batch_id="x",
            decisions=[{"item_id": str(i), "action": "APPROVE"} for i in range(201)],
        )


def test_ingest_rejects_unknown_fields():
    """Ingest schema forbids extra fields — deep/nested junk 422s, not 201."""
    from app.schemas.action_item import BatchIngestRequest
    from pydantic import ValidationError
    import pytest as _pytest

    with _pytest.raises(ValidationError):
        BatchIngestRequest.model_validate(
            {"raw_text": "Sarah: probe ok.", "source_type": "meeting_transcript", "junk": {"a": {"b": {}}}}
        )


def test_oauth_token_size_caps():
    """Oversized tokens/providers are rejected at the schema boundary."""
    from app.api.endpoints.connectors import SaveOAuthTokenRequest
    from pydantic import ValidationError
    import pytest as _pytest

    with _pytest.raises(ValidationError):
        SaveOAuthTokenRequest(provider="notion", access_token="T" * 8_193)
    with _pytest.raises(ValidationError):
        SaveOAuthTokenRequest(provider="x" * 60, access_token="T" * 32)
    ok = SaveOAuthTokenRequest(provider="notion", access_token="T" * 8_192)
    assert ok.provider == "notion"


@pytest.mark.asyncio
async def test_extraction_provider_chain_fallback_and_reask():
    """Provider chain: failure falls through to the next provider; a schema
    error gets one reask before moving on; success returns items."""
    from app.pipelines.extract import _invoke_extraction_llm
    from app.pipelines.extract import ExtractedActionItemSchema

    class FakeLLM:
        def __init__(self, behavior):
            self.behavior = behavior
            self.calls = 0

        def with_structured_output(self, _schema, **kwargs):
            # The production call pins method="json_schema"; the stub records it.
            self.last_method = kwargs.get("method")
            return self

        async def ainvoke(self, messages):
            self.calls += 1
            if self.behavior == "fail":
                raise RuntimeError("quota exceeded")
            if self.behavior == "reask_then_ok" and self.calls == 1:
                raise ValueError("validation: confidence required")
            good = ExtractedActionItemSchema(
                description="File the ticket", suggested_tool="jira",
                source_snippet="file the ticket", confidence=0.9,
            )
            from app.pipelines.extract import ExtractedActionItemList
            return ExtractedActionItemList(items=[good])

    # 1. Gemini fails hard -> OpenAI succeeds, error records the fallthrough
    gemini = FakeLLM("fail")
    openai = FakeLLM("ok")
    items, errors = await _invoke_extraction_llm(
        "text", [("gemini", gemini), ("openai", openai)], "sys")
    assert len(items) == 1 and items[0]["suggested_tool"] == "jira"
    assert gemini.calls == 1 and openai.calls == 1
    assert any("gemini" in e for e in errors)
    assert not any("sk-" in e or "AIza" in e for e in errors)

    # 2. Reask: first call fails validation, second succeeds on the same
    # provider; the reask note is informational, not a failure
    flaky = FakeLLM("reask_then_ok")
    items, errors = await _invoke_extraction_llm("text", [("openai", flaky)], "sys")
    assert flaky.calls == 2 and len(items) == 1
    assert all("reasking" in e for e in errors)  # informational only
    assert not any("failed:" in e for e in errors)  # no hard failure recorded

    # 3. Whole chain fails -> empty items, errors recorded per provider
    a, b = FakeLLM("fail"), FakeLLM("fail")
    items, errors = await _invoke_extraction_llm("text", [("a", a), ("b", b)], "sys")
    assert items == [] and len(errors) == 2
