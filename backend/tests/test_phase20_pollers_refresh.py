"""Phase 20 — poller lifecycle + generalized Google token refresh.

The ambient pollers (Gmail 15-min poll, Slack 5-min listen cycle) run as
fixed-id Temporal Schedules. They could be armed but never disarmed; now
Stop pauses the schedule (config kept, Start re-arms) and GET /pollers
reports armed/running/paused/missing for each. The Google token refresh
previously existed only for Gmail; it is generalized so the calendar and
google_tasks providers refresh through the same oauth2.googleapis.com
flow with the one shared Google OAuth client.
"""
from datetime import datetime, timedelta, timezone

import pytest


GMAIL_SCHEDULE_ID = "kairos-gmail-poll"
SLACK_SCHEDULE_ID = "kairos-slack-listen"


async def _delete_schedules_if_present():
    """Best-effort cleanup so tests are order-independent against live
    Temporal (a leftover paused schedule from a prior run would leak)."""
    from temporalio.service import RPCError, RPCStatusCode

    from app.temporal.worker import get_temporal_client

    client = await get_temporal_client()
    for sid in (GMAIL_SCHEDULE_ID, SLACK_SCHEDULE_ID):
        try:
            handle = client.get_schedule_handle(sid)
            await handle.delete()
        except RPCError as e:
            if e.status != RPCStatusCode.NOT_FOUND:
                raise


@pytest.mark.asyncio
async def test_pollers_endpoint_shape_on_missing_schedules():
    """GET /api/connectors/pollers always returns exactly the gmail+slack
    two-key shape; a never-armed schedule reads {armed: false, missing}."""
    from starlette.testclient import TestClient
    from app.main import app

    await _delete_schedules_if_present()

    with TestClient(app) as client:
        res = client.get("/api/connectors/pollers")
        assert res.status_code == 200
        body = res.json()
        assert set(body.keys()) == {"gmail", "slack"}
        assert body["gmail"] == {"armed": False, "state": "missing"}
        assert body["slack"] == {"armed": False, "state": "missing"}


@pytest.mark.asyncio
async def test_stop_missing_schedule_is_404():
    """Stopping a schedule that was never armed is a clean 404, not 503."""
    from starlette.testclient import TestClient
    from app.main import app

    await _delete_schedules_if_present()

    with TestClient(app) as client:
        gmail = client.post("/api/connectors/gmail/schedule/stop")
        assert gmail.status_code == 404

        slack = client.post("/api/connectors/slack/schedule/stop")
        assert slack.status_code == 404


@pytest.mark.asyncio
async def test_arm_pause_pollers_shows_paused():
    """Full lifecycle against live Temporal: arm the Gmail schedule via the
    existing setup endpoint, pause it via stop, and see /pollers report
    armed + paused. The stop response carries the schedule id.

    NOTE: requires the live Temporal server (conftest boots against it);
    if Temporal is unreachable the arm leg 503s — that is a genuine
    environment failure, not a skip-worthy condition.
    """
    from starlette.testclient import TestClient
    from app.main import app

    await _delete_schedules_if_present()

    with TestClient(app) as client:
        armed = client.post("/api/connectors/gmail/schedule")
        assert armed.status_code == 200, armed.text
        assert armed.json()["status"] == "scheduled"

        running = client.get("/api/connectors/pollers")
        assert running.status_code == 200
        assert running.json()["gmail"] == {"armed": True, "state": "running"}

        stopped = client.post("/api/connectors/gmail/schedule/stop")
        assert stopped.status_code == 200
        assert stopped.json() == {"status": "paused", "schedule": GMAIL_SCHEDULE_ID}

        paused = client.get("/api/connectors/pollers")
        assert paused.status_code == 200
        assert paused.json()["gmail"] == {"armed": True, "state": "paused"}

        # Start on a paused schedule must resume it (not "kept" paused).
        resumed = client.post("/api/connectors/gmail/schedule")
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["status"] == "scheduled"

        running_again = client.get("/api/connectors/pollers")
        assert running_again.status_code == 200
        assert running_again.json()["gmail"] == {"armed": True, "state": "running"}

    await _delete_schedules_if_present()


@pytest.mark.asyncio
async def test_refresh_google_token_for_calendar_row(monkeypatch):
    """The generalized refresh helper drives the google_calendar vault row:
    an expired row with a refresh token and env creds triggers a POST to
    oauth2.googleapis.com/token, stores the new access token, and pushes
    expires_at into the future — all without real network."""
    from sqlalchemy import delete as _delete
    from sqlalchemy import select as _select

    from app.core.security import decrypt_token, encrypt_token
    from app.db.models import OAuthTokenModel
    from app.db.session import async_session_factory
    import httpx

    from app.temporal.activities import _refresh_google_token

    async with async_session_factory() as session:
        await session.execute(
            _delete(OAuthTokenModel).where(OAuthTokenModel.provider == "google_calendar")
        )
        await session.commit()

    expired = datetime.now(timezone.utc) - timedelta(seconds=120)
    async with async_session_factory() as session:
        session.add(OAuthTokenModel(
            provider="google_calendar",
            access_token_enc=encrypt_token("stale-calendar-access"),
            refresh_token_enc=encrypt_token("cal-refresh-1"),
            expires_at=expired,
        ))
        await session.commit()

    monkeypatch.setenv("GMAIL_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "test-client-secret")

    posted: dict = {}

    class _FakeResponse:
        is_success = True
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {"access_token": "fresh-calendar-access", "expires_in": 3600}

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def post(self, url: str, data: dict | None = None):
            posted["url"] = url
            posted["data"] = data
            return _FakeResponse()

    # The helper imports httpx lazily inside its body; the import resolves
    # through sys.modules, so patching httpx.AsyncClient is what it sees.
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    token = await _refresh_google_token("google_calendar")

    assert token == "fresh-calendar-access"
    assert posted["url"] == "https://oauth2.googleapis.com/token"
    assert posted["data"] == {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "refresh_token": "cal-refresh-1",
        "grant_type": "refresh_token",
    }

    async with async_session_factory() as session:
        rows = await session.scalars(
            _select(OAuthTokenModel).where(OAuthTokenModel.provider == "google_calendar")
        )
        rec = rows.first()
        assert decrypt_token(rec.access_token_enc) == "fresh-calendar-access"
        assert rec.expires_at is not None
        assert rec.expires_at > datetime.now(timezone.utc) + timedelta(minutes=30)
        await session.delete(rec)
        await session.commit()


@pytest.mark.asyncio
async def test_refresh_google_token_no_row_returns_none():
    """A provider with no vault row refreshes nothing: None, no exception."""
    from sqlalchemy import delete as _delete

    from app.db.models import OAuthTokenModel
    from app.db.session import async_session_factory
    from app.temporal.activities import _get_calendar_access_token, _refresh_google_token

    async with async_session_factory() as session:
        await session.execute(
            _delete(OAuthTokenModel).where(OAuthTokenModel.provider == "google_calendar")
        )
        await session.commit()

    assert await _refresh_google_token("google_calendar") is None
    assert await _get_calendar_access_token() is None


@pytest.mark.asyncio
async def test_google_tasks_falls_back_to_calendar_row():
    """Without a google_tasks row, the tasks helper serves from the
    google_calendar row (the bundled calendar+tasks grant)."""
    from sqlalchemy import delete as _delete

    from app.core.security import encrypt_token
    from app.db.models import OAuthTokenModel
    from app.db.session import async_session_factory
    from app.temporal.activities import _get_google_tasks_access_token

    async with async_session_factory() as session:
        await session.execute(
            _delete(OAuthTokenModel).where(
                OAuthTokenModel.provider.in_(["google_tasks", "google_calendar"])
            )
        )
        # Far-future expiry: no refresh leg, no env creds, no network.
        session.add(OAuthTokenModel(
            provider="google_calendar",
            access_token_enc=encrypt_token("calendar-access-live"),
            refresh_token_enc=encrypt_token("cal-refresh"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        await session.commit()

    token = await _get_google_tasks_access_token()
    assert token == "calendar-access-live"

    async with async_session_factory() as session:
        await session.execute(
            _delete(OAuthTokenModel).where(
                OAuthTokenModel.provider.in_(["google_tasks", "google_calendar"])
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_poller_paths_503_redacted_on_transport_failure(monkeypatch):
    """Dead Temporal (connection refused, not RPCError) must 503 with the
    credential stripped — never a raw 500. Hostnames stay: diagnostic,
    not secret."""
    async def _dead():
        raise ConnectionError("refused by internal-host token=SECRET123")

    monkeypatch.setattr("app.temporal.worker.get_temporal_client", _dead)
    from starlette.testclient import TestClient
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        res = client.get("/api/connectors/pollers")
        assert res.status_code == 503
        assert "SECRET123" not in res.text

        stop = client.post("/api/connectors/gmail/schedule/stop")
        assert stop.status_code == 503
        assert "SECRET123" not in stop.text


@pytest.mark.asyncio
async def test_setup_vanished_schedule_is_404_not_false_success(monkeypatch):
    """Create reports AlreadyRunning but the row is gone: the API must
    404 (retry recreates) instead of claiming 'resumed'."""
    from temporalio.client import ScheduleAlreadyRunningError
    from temporalio.service import RPCError, RPCStatusCode

    class _Handle:
        async def describe(self):
            raise RPCError("gone", RPCStatusCode.NOT_FOUND, b"")

    class _Client:
        def get_schedule_handle(self, *a, **k):
            return _Handle()

        async def create_schedule(self, *a, **k):
            raise ScheduleAlreadyRunningError()

    async def _fake_client():
        return _Client()

    monkeypatch.setattr("app.temporal.worker.get_temporal_client", _fake_client)
    # setup imports get_temporal_client from worker at call time
    monkeypatch.setattr(
        "app.api.endpoints.connectors.get_temporal_client", _fake_client, raising=False
    )
    from starlette.testclient import TestClient
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        res = client.post("/api/connectors/gmail/schedule")
        # 404 (the app's 404 handler generalizes the detail by design).
        assert res.status_code == 404
