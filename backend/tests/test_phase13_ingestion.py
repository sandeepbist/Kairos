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
