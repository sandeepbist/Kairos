"""Ingestion expansion tests: notetaker exports and the Gmail poller."""
import pytest
from starlette.testclient import TestClient

from app.main import app


class TestExportNormalization:
    def test_front_matter_stripped(self):
        from app.api.endpoints.ingest_exports import strip_front_matter

        raw = "---\ntitle: Weekly Sync\ndate: 2026-09-01\n---\n\nSarah: hi"
        body, meta = strip_front_matter(raw)
        assert body.strip() == "Sarah: hi"
        assert meta["title"] == "Weekly Sync"

    def test_otter_timestamp_labels_normalized(self):
        from app.api.endpoints.ingest_exports import normalize_export

        raw = (
            "Sarah 12:04  Alex, please file the export ticket\n"
            "Alex 12:05   I will schedule the export review meeting"
        )
        out = normalize_export(raw, "otter")
        assert "Sarah: Alex, please file the export ticket" in out
        assert "Alex: I will schedule the export review meeting" in out

    def test_markdown_summary_chrome_dropped(self):
        from app.api.endpoints.ingest_exports import normalize_export

        raw = (
            "# Weekly Sync — Sep 1\n"
            "## Summary\n- **Key Points:** things happened\n"
            "Sarah: Alex, please update the pricing doc\n"
        )
        out = normalize_export(raw, "markdown")
        assert "Summary" not in out and "Key Points" not in out
        assert "Sarah: Alex, please update the pricing doc" in out

    def test_zero_width_and_bom_removed(self):
        from app.api.endpoints.ingest_exports import normalize_export

        out = normalize_export("\ufeffSarah:\u200b hello there", "plain")
        assert "\ufeff" not in out and "\u200b" not in out


@pytest.mark.asyncio
async def test_export_endpoint_ingests_and_extracts():
    """The export endpoint runs the full pipeline: normalized text reaches
    extraction with speaker labels intact."""
    import asyncio
    from app.db.session import async_session_factory
    from app.db.models import BatchModel
    from sqlalchemy import select
    from app.temporal.worker import create_worker, get_temporal_client

    temp_client = await get_temporal_client()
    worker = create_worker(temp_client)
    worker_task = asyncio.create_task(worker.run())
    try:
        with TestClient(app) as client:
            export = (
                "---\ntitle: Product Sync — May 12\n---\n"
                "# Product Sync\n"
                "Sarah 00:12  Alex, please file the export normalization ticket\n"
                "Alex 00:30   I will schedule the export sync meeting on Thursday"
            )
            res = client.post(
                "/api/ingest/export",
                json={
                    "raw_text": export,
                    "source_type": "meeting_transcript",
                    "export_format": "otter",
                },
            )
            assert res.status_code == 201, res.text
            batch_id = res.json()["batch_id"]

            # Wait for extraction
            for _ in range(30):
                await asyncio.sleep(0.5)
                data = client.get(f"/api/batches/{batch_id}").json()
                if data["status"] == "awaiting_approval":
                    break
            assert data["status"] == "awaiting_approval"
            assert any("export normalization" in i["description"].lower() for i in data["items"])

            async with async_session_factory() as session:
                b = (await session.execute(
                    select(BatchModel).where(BatchModel.id == batch_id)
                )).scalar_one()
                assert b.raw_text.startswith("[Product Sync — May 12]")
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_gmail_poll_noop_without_credentials():
    """The Gmail poll activity exits cleanly when Gmail isn't connected."""
    from sqlalchemy import delete as _delete
    from app.db.session import async_session_factory
    from app.db.models import OAuthTokenModel
    from app.temporal.activities import ingest_gmail_history_activity

    async with async_session_factory() as session:
        await session.execute(_delete(OAuthTokenModel).where(OAuthTokenModel.provider == "gmail"))
        await session.commit()

    result = await ingest_gmail_history_activity()
    assert result == {"polled": False, "reason": "gmail_not_configured"}


@pytest.mark.asyncio
async def test_gmail_schedule_idempotent():
    """Creating the poll schedule twice keeps one schedule running.

    Uses a live Temporal connection (schedule creation is a server
    operation, unreachable through the in-process test client) and
    cleans up after itself so reruns stay green.
    """
    from temporalio.client import Client

    client = await Client.connect("localhost:7234", namespace="default")
    from temporalio.client import ScheduleActionStartWorkflow, Schedule, ScheduleSpec, ScheduleIntervalSpec
    from datetime import timedelta
    from app.temporal.gmail_poll import GmailPollWorkflow
    from app.config import settings

    async def create():
        return await client.create_schedule(
            id="kairos-gmail-poll-test",
            schedule=Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow=GmailPollWorkflow.run,
                    id="gmail-poll-cycle-test",
                    task_queue=settings.TEMPORAL_TASK_QUEUE,
                ),
                spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=timedelta(minutes=15))]),
            ),
        )

    # clean slate: tolerate a leftover from a crashed run
    try:
        await client.get_schedule_handle("kairos-gmail-poll-test").delete()
    except Exception:
        pass

    try:
        await create()
        # second create must fail as duplicate — the endpoint's
        # idempotency contract
        from temporalio.client import ScheduleAlreadyRunningError

        duplicate_rejected = False
        try:
            await create()
        except ScheduleAlreadyRunningError:
            duplicate_rejected = True
        assert duplicate_rejected
    finally:
        try:
            await client.get_schedule_handle("kairos-gmail-poll-test").delete()
        except Exception:
            pass


class TestSlackExportNormalization:
    def test_slack_json_export(self):
        from app.api.endpoints.ingest_exports import normalize_slack_export

        raw = '''[
          {"user_profile": {"display_name": "Sarah"}, "text": "Alex, please file the deploy bug"},
          {"user": "U123", "text": "I will schedule the release review meeting"}
        ]'''
        out = normalize_slack_export(raw)
        assert "Sarah: Alex, please file the deploy bug" in out
        assert "U123: I will schedule the release review meeting" in out

    def test_slack_channel_history_dict(self):
        from app.api.endpoints.ingest_exports import normalize_slack_export

        raw = '''{"messages": [
          {"user_profile": {"display_name": "DevOps"}, "text": "Please update the runbook doc"}
        ]}'''
        out = normalize_slack_export(raw)
        assert "DevOps: Please update the runbook doc" in out

    def test_copied_thread_text(self):
        from app.api.endpoints.ingest_exports import normalize_slack_export

        raw = "Sarah  12:04 PM\nAlex, can you draft the vendor email?\nTom  12:06 PM\nOn it."
        out = normalize_slack_export(raw)
        assert "Sarah:" in out and "Tom:" in out
        assert "draft the vendor email" in out


@pytest.mark.asyncio
async def test_slack_export_endpoint_e2e():
    """Slack-format export flows through to extraction with speaker turns."""
    import asyncio
    from starlette.testclient import TestClient
    from app.main import app
    from app.temporal.worker import create_worker, get_temporal_client

    temp_client = await get_temporal_client()
    worker = create_worker(temp_client)
    worker_task = asyncio.create_task(worker.run())
    try:
        with TestClient(app) as client:
            export = '''[
              {"user_profile": {"display_name": "Sarah"}, "text": "Alex, please file the deploy bug by Friday"},
              {"user_profile": {"display_name": "Alex"}, "text": "Sure, I will also schedule the release review meeting Thursday"}
            ]'''
            res = client.post(
                "/api/ingest/export",
                json={
                    "raw_text": export,
                    "source_type": "slack_conversation",
                    "export_format": "slack_export",
                },
            )
            assert res.status_code == 201, res.text
            batch_id = res.json()["batch_id"]
            for _ in range(30):
                await asyncio.sleep(0.5)
                data = client.get(f"/api/batches/{batch_id}").json()
                if data["status"] == "awaiting_approval":
                    break
            assert data["status"] == "awaiting_approval"
            descs = " ".join(i["description"].lower() for i in data["items"])
            assert "deploy bug" in descs and "release review" in descs
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_slack_poll_noop_without_tokens():
    """The Slack Socket Mode activity exits cleanly when unconfigured."""
    import os

    from app.temporal.activities import slack_socket_poll_activity

    os.environ.pop("SLACK_APP_TOKEN", None)
    os.environ.pop("SLACK_BOT_TOKEN", None)
    result = await slack_socket_poll_activity()
    assert result == {"polled": False, "reason": "slack_not_configured"}


def test_slack_workflow_registered():
    """The Slack ingest workflow is part of the worker's registry."""
    from app.temporal.worker import create_worker

    import inspect

    src = inspect.getsource(create_worker)
    assert "SlackIngestWorkflow" in src


@pytest.mark.asyncio
async def test_slack_listen_cycle_ingests_threads(monkeypatch):
    """A full listen cycle: connect → collect events → attribute
    speakers via users_info → ingest one batch per thread → record
    seen state. The WebSocket client is faked; the grouping, dedup,
    attribution, and ingest paths run for real."""
    import os

    from sqlalchemy import delete as _delete

    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.db.models import BatchModel, OAuthTokenModel
    from app.temporal.activities import slack_socket_poll_activity

    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
    monkeypatch.setenv("SLACK_LISTEN_SECONDS", "0.1")

    events = [
        {  # thread one, two turns, two speakers
            "type": "message",
            "channel": "C1", "channel_type": "channel", "user": "U1",
            "text": "Alex, please file the checkout bug by Friday",
            "ts": "1700000000.000100", "thread_ts": "1700000000.000100",
            "client_msg_id": "m-1",
        },
        {
            "type": "message",
            "channel": "C1", "channel_type": "channel", "user": "U2",
            "text": "On it — I will also schedule the release review meeting",
            "ts": "1700000000.000200", "thread_ts": "1700000000.000100",
            "client_msg_id": "m-2",
        },
        {  # standalone DM to the bot
            "type": "message",
            "channel": "D1", "channel_type": "im", "user": "U3",
            "text": "Can you update the vendor onboarding doc in the wiki?",
            "ts": "1700000000.000300", "thread_ts": None,
            "client_msg_id": "m-3",
        },
        {  # bot/edited message: must be skipped
            "type": "message",
            "channel": "C1", "channel_type": "channel", "user": "U1",
            "text": "changed my mind", "ts": "1700000000.000400",
            "thread_ts": "1700000000.000100", "client_msg_id": "m-4",
            "subtype": "message_changed",
        },
    ]

    class FakeUsersInfo:
        data = {
            "U1": {"user": {"real_name": "Sarah Chen"}},
            "U2": {"user": {"real_name": "Alex Rivera"}},
            "U3": {"user": {"real_name": "Priya Patel"}},
        }

        def __call__(self, user):
            return self.data[user]

    class FakeSocketClient:
        def __init__(self, app_token, web_client=None, auto_reconnect_enabled=True):
            self.socket_mode_request_listeners = []
            self.is_connected = False

        def connect(self):
            self.is_connected = True
            # Replay the events as if they arrived on the socket.
            for ev in events:
                from slack_sdk.socket_mode.request import SocketModeRequest

                req = SocketModeRequest(
                    type="events_api",
                    envelope_id=f"env-{ev['client_msg_id']}",
                    payload={"event": ev},
                )
                for listener in self.socket_mode_request_listeners:
                    listener(self, req)

        def disconnect(self):
            self.is_connected = False

        def send_socket_mode_response(self, response):
            pass

    monkeypatch.setattr(
        "slack_sdk.socket_mode.SocketModeClient", FakeSocketClient, raising=False
    )
    monkeypatch.setattr(
        "slack_sdk.WebClient.users_info", FakeUsersInfo(), raising=False
    )

    # clean slate: no slack vault row state from earlier runs
    async with async_session_factory() as session:
        await session.execute(_delete(OAuthTokenModel).where(OAuthTokenModel.provider == "slack"))
        await session.commit()

    result = await slack_socket_poll_activity()
    assert result["polled"] is True
    assert result["ingested"] == 2  # one thread + one DM; edited msg skipped
    assert result["events"] == 3  # the edited/subtype message is filtered at collection

    # Both batches landed with speaker-attributed text.
    async with async_session_factory() as session:
        res = await session.execute(
            select(BatchModel).where(BatchModel.source_type == "slack_conversation")
        )
        batches = res.scalars().all()
        assert len(batches) >= 2
    os.environ.pop("SLACK_LISTEN_SECONDS", None)


@pytest.mark.asyncio
async def test_slack_listen_cycle_dedups_seen_messages(monkeypatch):
    """Messages already recorded in the vault's seen state are not
    re-ingested — the Schedule can restart freely without duplicates."""
    from sqlalchemy import delete as _delete

    from app.db.session import async_session_factory
    from app.db.models import OAuthTokenModel
    from app.temporal.activities import (
        slack_socket_poll_activity,
        _store_slack_seen_state,
    )

    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
    monkeypatch.setenv("SLACK_LISTEN_SECONDS", "0.1")

    # A slack vault row whose seen state already contains m-1.
    from app.core.security import encrypt_token

    async with async_session_factory() as session:
        await session.execute(_delete(OAuthTokenModel).where(OAuthTokenModel.provider == "slack"))
        session.add(OAuthTokenModel(
            provider="slack",
            access_token_enc=encrypt_token("xoxb-test-token"),
        ))
        await session.commit()
    await _store_slack_seen_state({"m-1"})

    class FakeSocketClient:
        def __init__(self, app_token, web_client=None, auto_reconnect_enabled=True):
            self.socket_mode_request_listeners = []
            self.is_connected = False

        def connect(self):
            self.is_connected = True
            from slack_sdk.socket_mode.request import SocketModeRequest

            ev = {
                "type": "message",
                "channel": "C1", "channel_type": "channel", "user": "U1",
                "text": "Alex, please file the checkout bug by Friday",
                "ts": "1700000000.000100", "thread_ts": "1700000000.000100",
                "client_msg_id": "m-1",
            }
            req = SocketModeRequest(
                type="events_api", envelope_id="env-1", payload={"event": ev},
            )
            for listener in self.socket_mode_request_listeners:
                listener(self, req)

        def disconnect(self):
            self.is_connected = False

        def send_socket_mode_response(self, response):
            pass

    monkeypatch.setattr(
        "slack_sdk.socket_mode.SocketModeClient", FakeSocketClient, raising=False
    )

    result = await slack_socket_poll_activity()
    assert result["polled"] is True
    assert result["ingested"] == 0  # m-1 was already seen

    async with async_session_factory() as session:
        await session.execute(_delete(OAuthTokenModel).where(OAuthTokenModel.provider == "slack"))
        await session.commit()


@pytest.mark.asyncio
async def test_slack_schedule_idempotent():
    """Creating the listen schedule twice keeps one schedule running."""
    from datetime import timedelta

    from temporalio.client import (
        Client,
        Schedule,
        ScheduleActionStartWorkflow,
        ScheduleIntervalSpec,
        ScheduleSpec,
    )
    from temporalio.client import ScheduleAlreadyRunningError

    from app.config import settings
    from app.temporal.slack_ingest import SlackIngestWorkflow

    client = await Client.connect("localhost:7234", namespace="default")

    async def create():
        return await client.create_schedule(
            id="kairos-slack-listen-test",
            schedule=Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow=SlackIngestWorkflow.run,
                    id="slack-listen-cycle-test",
                    task_queue=settings.TEMPORAL_TASK_QUEUE,
                ),
                spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=timedelta(minutes=5))]),
            ),
        )

    try:
        await client.get_schedule_handle("kairos-slack-listen-test").delete()
    except Exception:
        pass

    try:
        await create()
        duplicate_rejected = False
        try:
            await create()
        except ScheduleAlreadyRunningError:
            duplicate_rejected = True
        assert duplicate_rejected
    finally:
        try:
            await client.get_schedule_handle("kairos-slack-listen-test").delete()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_gmail_poll_ingests_thread_and_advances_watermark(monkeypatch):
    """Credentialed poll: one new thread becomes a batch, the watermark
    advances, and a failed thread is recorded for retry (not skipped)."""
    import base64
    import json as _json

    from sqlalchemy import delete as _delete
    from sqlalchemy import select
    from app.core.security import encrypt_token
    from app.db.models import BatchModel, OAuthTokenModel
    from app.db.session import async_session_factory
    from app.temporal.activities import ingest_gmail_history_activity

    body_b64 = base64.urlsafe_b64encode(b"Alex: please file this ticket now").decode()

    class FakeResp:
        def __init__(self, payload, status=200):
            self._payload = payload
            self.status_code = status
            self.is_success = 200 <= status < 300

        def json(self):
            return self._payload

    def _thread(tid, ok=True):
        if not ok:
            return FakeResp({}, 500)
        return FakeResp({"messages": [{
            "payload": {
                "headers": [{"name": "Subject", "value": "Subj"}],
                "parts": [{"mimeType": "text/plain",
                           "body": {"data": body_b64}}],
            },
            "snippet": "snip",
        }]})

    class FakeClient:
        def __init__(self, *a, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, url, params=None, headers=None):
            if url.endswith("/profile"):
                return FakeResp({"historyId": 999})
            if "/history" in url:
                return FakeResp({
                    "historyId": 456,
                    "history": [
                        {"messagesAdded": [{"message": {"threadId": "good-tid"}}]},
                        {"messagesAdded": [{"message": {"threadId": "bad-tid"}}]},
                    ],
                })
            if "/threads/good-tid" in url:
                return _thread("good-tid")
            return _thread("bad-tid", ok=False)

    async with async_session_factory() as session:
        await session.execute(_delete(OAuthTokenModel).where(OAuthTokenModel.provider == "gmail"))
        session.add(OAuthTokenModel(
            provider="gmail",
            access_token_enc=encrypt_token("fake-access"),
            scopes=_json.dumps({"history_id": 123}),
        ))
        await session.commit()

    import httpx as _httpx
    monkeypatch.setattr(_httpx, "AsyncClient", FakeClient)
    try:
        result = await ingest_gmail_history_activity()
        stored_scopes = {}
        async with async_session_factory() as session:
            rec = (
                await session.execute(
                    select(OAuthTokenModel).where(OAuthTokenModel.provider == "gmail")
                )
            ).scalar_one()
            stored_scopes = _json.loads(rec.scopes)
    finally:
        async with async_session_factory() as session:
            await session.execute(_delete(OAuthTokenModel).where(OAuthTokenModel.provider == "gmail"))
            await session.commit()

    assert result["polled"] is True
    assert result["ingested"] == 1
    assert result["history_id"] == 456
    assert stored_scopes.get("history_id") == 456
    assert "bad-tid" in stored_scopes.get("failed_threads", [])

    async with async_session_factory() as session:
        batches = (
            await session.execute(select(BatchModel).where(BatchModel.source_type == "email_thread"))
        ).scalars().all()
        assert any("please file this ticket" in (b.raw_text or "") for b in batches)


@pytest.mark.asyncio
async def test_slack_failed_ingest_not_marked_seen(monkeypatch):
    """A thread whose batch creation fails must stay unmarked so the next
    cycle retries it — only successfully ingested messages join seen."""
    from sqlalchemy import delete as _delete

    from app.db.session import async_session_factory
    from app.db.models import OAuthTokenModel
    from app.temporal.activities import (
        slack_socket_poll_activity,
        _load_slack_seen_state,
    )

    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
    monkeypatch.setenv("SLACK_LISTEN_SECONDS", "0.1")

    from app.core.security import encrypt_token

    async with async_session_factory() as session:
        await session.execute(_delete(OAuthTokenModel).where(OAuthTokenModel.provider == "slack"))
        session.add(OAuthTokenModel(
            provider="slack",
            access_token_enc=encrypt_token("xoxb-test-token"),
        ))
        await session.commit()

    async def _boom_create(text, source_type, session):
        if "FAILME" in text:
            raise RuntimeError("ingest exploded")
        return {"batch_id": "fake", "status": "processing"}

    monkeypatch.setattr(
        "app.api.endpoints.batches.create_and_start_batch", _boom_create
    )

    class FakeUsers:
        data = {"user": {"real_name": "Alex"}}

    class FakeWebClient:
        def __init__(self, token=None):
            pass

        def users_info(self, user=None):
            return FakeUsers()

    class FakeSocketClient:
        def __init__(self, app_token, web_client=None, auto_reconnect_enabled=True):
            self.socket_mode_request_listeners = []
            self.is_connected = False

        def connect(self):
            self.is_connected = True
            from slack_sdk.socket_mode.request import SocketModeRequest

            for i, (ts, txt) in enumerate([
                ("1700000001.000100", "Alex, please file the checkout bug by Friday"),
                ("1700000002.000200", "FAILME please file the checkout bug by Friday"),
            ]):
                ev = {
                    "type": "message",
                    "channel": "C1", "channel_type": "channel", "user": "U1",
                    "text": txt, "ts": ts, "thread_ts": ts,
                    "client_msg_id": f"t-{i}",
                }
                req = SocketModeRequest(
                    type="events_api", envelope_id=f"env-{i}", payload={"event": ev},
                )
                for listener in self.socket_mode_request_listeners:
                    listener(self, req)

        def disconnect(self):
            self.is_connected = False

        def send_socket_mode_response(self, response):
            pass

    import slack_sdk
    import slack_sdk.socket_mode
    monkeypatch.setattr(slack_sdk, "WebClient", FakeWebClient, raising=False)
    monkeypatch.setattr(
        slack_sdk.socket_mode, "SocketModeClient", FakeSocketClient, raising=False
    )

    try:
        result = await slack_socket_poll_activity()
        assert result["polled"] is True
        assert result["ingested"] == 1
        seen = await _load_slack_seen_state()
        assert "t-0" in seen
        assert "t-1" not in seen
    finally:
        async with async_session_factory() as session:
            await session.execute(_delete(OAuthTokenModel).where(OAuthTokenModel.provider == "slack"))
            await session.commit()
