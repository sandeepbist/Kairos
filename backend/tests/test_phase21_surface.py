"""Phase 21 — the "surface" pass: ledger HTTP routes, batch summary,
per-item error surfacing, and connector test-connection.

The frontend dashboard now reads ledger tasks over plain HTTP (instead
of only through the MCP tool path), shows a review-queue badge, renders
the reason an executed item failed, and can probe a single connector
from the Settings screen. This suite pins each contract:

- GET /api/ledger/tasks (+status filter, default hides soft-deleted)
- POST /api/ledger/tasks/{id}/complete, DELETE /api/ledger/tasks/{id}
- GET /api/batches/summary (awaiting_approval count)
- GET /api/batches/{id} items gain error: str|None
- GET /api/history log dicts gain error
- POST /api/connectors/test with {tool}

Fixtures follow the phase19/20 style: direct async-session row inserts,
TestClient against the shared app. No credential-shaped literals —
placeholder tokens are built at runtime from uuid4.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest


def _runtime_token(prefix: str = "tok") -> str:
    """Runtime-built placeholder; no credential literal in source."""
    return f"{prefix}-{uuid.uuid4().hex}"


async def _insert_ledger_row(
    title: str = "Phase 21 probe task",
    status: str = "open",
    created_at: datetime | None = None,
) -> str:
    """Inserts one TaskLedgerModel row directly; returns its id."""
    from app.db.models import TaskLedgerModel
    from app.db.session import async_session_factory

    task_id = str(uuid.uuid4())
    async with async_session_factory() as session:
        session.add(TaskLedgerModel(
            id=task_id,
            title=title,
            notes="inserted by test_phase21_surface",
            priority="medium",
            due_date=None,
            status=status,
            created_at=created_at or datetime.now(timezone.utc),
            updated_at=created_at or datetime.now(timezone.utc),
        ))
        await session.commit()
    return task_id


async def _insert_batch_with_item_and_log(
    batch_status: str = "awaiting_approval",
    log_error: str | None = None,
) -> tuple[str, str, str]:
    """Creates batch + one action item (+ optionally one execution log).

    Returns (batch_id, item_id, log_id). The log, when present, is the
    item's failed execution carrying `log_error`.
    """
    from app.db.models import BatchModel, ActionItemModel, ExecutionLogModel
    from app.db.session import async_session_factory

    batch_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    log_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        session.add(BatchModel(
            id=batch_id,
            source_type="meeting_transcript",
            raw_text="Test batch for phase 21 surface tests.",
            status=batch_status,
            created_at=now,
            updated_at=now,
        ))
        session.add(ActionItemModel(
            id=item_id,
            batch_id=batch_id,
            description="Phase 21 item for error surfacing",
            suggested_tool="notion",
            tool_payload={},
            source_snippet="Phase 21 item",
            status="failed" if log_error is not None else "pending",
            created_at=now,
            updated_at=now,
        ))
        if log_error is not None:
            session.add(ExecutionLogModel(
                id=log_id,
                item_id=item_id,
                batch_id=batch_id,
                tool="notion",
                status="failed",
                idempotency_hash=uuid.uuid4().hex,
                external_url=None,
                item_description="Phase 21 item for error surfacing",
                latency_ms=12,
                error=log_error,
                executed_at=now,
            ))
        await session.commit()
    return batch_id, item_id, log_id


# ── Ledger routes ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ledger_list_returns_row_and_shape():
    """GET /api/ledger/tasks returns the row with the exact contract keys,
    newest first, and external_url pointing at the ledger task URI."""
    from starlette.testclient import TestClient
    from app.main import app

    task_id = await _insert_ledger_row(title="Surface list probe")

    with TestClient(app) as client:
        res = client.get("/api/ledger/tasks")
        assert res.status_code == 200
        body = res.json()
        assert isinstance(body, list)
        match = next((t for t in body if t["id"] == task_id), None)
        assert match is not None
        assert set(match.keys()) == {
            "id", "title", "notes", "priority", "due_date", "status",
            "external_url", "created_at", "updated_at",
        }
        assert match["title"] == "Surface list probe"
        assert match["status"] == "open"
        assert match["external_url"] == f"task_ledger://tasks/{task_id}"
        # Datetimes serialized as ISO strings.
        assert isinstance(match["created_at"], str)
        assert "T" in match["created_at"]


@pytest.mark.asyncio
async def test_ledger_status_filter_and_default_hides_deleted():
    """?status= filters exactly; the default list never includes
    soft-deleted rows, but ?status=deleted surfaces the trash view."""
    from starlette.testclient import TestClient
    from app.main import app

    open_id = await _insert_ledger_row(title="Filter probe open", status="open")
    completed_id = await _insert_ledger_row(title="Filter probe done", status="completed")
    deleted_id = await _insert_ledger_row(title="Filter probe gone", status="deleted")

    with TestClient(app) as client:
        default_list = client.get("/api/ledger/tasks").json()
        default_ids = {t["id"] for t in default_list}
        assert open_id in default_ids
        assert completed_id in default_ids
        assert deleted_id not in default_ids

        open_only = client.get("/api/ledger/tasks?status=open").json()
        assert open_id in {t["id"] for t in open_only}
        assert completed_id not in {t["id"] for t in open_only}
        assert deleted_id not in {t["id"] for t in open_only}

        trash = client.get("/api/ledger/tasks?status=deleted").json()
        trash_ids = {t["id"] for t in trash}
        assert deleted_id in trash_ids
        assert open_id not in trash_ids


@pytest.mark.asyncio
async def test_ledger_complete_flips_status_and_updates_timestamp():
    """POST .../complete returns {status: completed, task_id} and the
    row shows completed with a moved updated_at."""
    from starlette.testclient import TestClient
    from app.main import app
    from app.db.models import TaskLedgerModel
    from app.db.session import async_session_factory

    stale = datetime.now(timezone.utc) - timedelta(days=30)
    task_id = await _insert_ledger_row(title="Complete probe", created_at=stale)

    with TestClient(app) as client:
        res = client.post(f"/api/ledger/tasks/{task_id}/complete")
        assert res.status_code == 200
        assert res.json() == {"status": "completed", "task_id": task_id}

        listed = client.get("/api/ledger/tasks?status=completed").json()
        match = next(t for t in listed if t["id"] == task_id)
        assert match["status"] == "completed"

    async with async_session_factory() as session:
        from sqlalchemy import select
        rows = await session.scalars(
            select(TaskLedgerModel).where(TaskLedgerModel.id == task_id)
        )
        row = rows.first()
        assert row.status == "completed"
        assert row.updated_at > stale + timedelta(days=1)


@pytest.mark.asyncio
async def test_ledger_delete_soft_deletes_and_hides_from_default():
    """DELETE ... returns {status: deleted, task_id}; the row stays in
    the table (soft delete) but leaves the default list; re-delete 404s."""
    from starlette.testclient import TestClient
    from app.main import app
    from sqlalchemy import select
    from app.db.models import TaskLedgerModel
    from app.db.session import async_session_factory

    task_id = await _insert_ledger_row(title="Delete probe")

    with TestClient(app) as client:
        res = client.delete(f"/api/ledger/tasks/{task_id}")
        assert res.status_code == 200
        assert res.json() == {"status": "deleted", "task_id": task_id}

        default_ids = {t["id"] for t in client.get("/api/ledger/tasks").json()}
        assert task_id not in default_ids

        again = client.delete(f"/api/ledger/tasks/{task_id}")
        assert again.status_code == 404

    async with async_session_factory() as session:
        rows = await session.scalars(
            select(TaskLedgerModel).where(TaskLedgerModel.id == task_id)
        )
        row = rows.first()
        assert row is not None, "delete must be soft — row retained"
        assert row.status == "deleted"


@pytest.mark.asyncio
async def test_ledger_404s_for_missing_and_deleted():
    """Complete 404s for unknown ids and for soft-deleted rows."""
    from starlette.testclient import TestClient
    from app.main import app

    deleted_id = await _insert_ledger_row(title="Complete-after-delete", status="deleted")
    missing_id = str(uuid.uuid4())

    with TestClient(app) as client:
        missing_complete = client.post(f"/api/ledger/tasks/{missing_id}/complete")
        assert missing_complete.status_code == 404

        missing_delete = client.delete(f"/api/ledger/tasks/{missing_id}")
        assert missing_delete.status_code == 404

        deleted_complete = client.post(f"/api/ledger/tasks/{deleted_id}/complete")
        assert deleted_complete.status_code == 404


# ── Batches summary + item error surfacing ───────────────────────────


@pytest.mark.asyncio
async def test_batches_summary_counts_awaiting_approval():
    """GET /api/batches/summary counts only awaiting_approval rows —
    completed/processing batches must not inflate the badge."""
    from starlette.testclient import TestClient
    from app.main import app
    from app.db.models import BatchModel
    from app.db.session import async_session_factory

    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        for status_value in ("awaiting_approval", "awaiting_approval", "completed"):
            session.add(BatchModel(
                id=str(uuid.uuid4()),
                source_type="meeting_transcript",
                raw_text="Summary count probe",
                status=status_value,
                created_at=now,
                updated_at=now,
            ))
        await session.commit()

    with TestClient(app) as client:
        # Two rows exist from other suites' data too; count exactly what
        # the DB holds at request time via a second direct query.
        res = client.get("/api/batches/summary")
        assert res.status_code == 200
        body = res.json()
        assert set(body.keys()) == {"awaiting_approval"}
        assert isinstance(body["awaiting_approval"], int)

        from sqlalchemy import select, func
        async with async_session_factory() as session:
            expected = int(await session.scalar(
                select(func.count()).select_from(BatchModel).where(
                    BatchModel.status == "awaiting_approval"
                )
            ))
        assert body["awaiting_approval"] == expected
        assert expected >= 2, "fixture inserted two awaiting_approval rows"


@pytest.mark.asyncio
async def test_summary_route_not_swallowed_by_batch_id_route():
    """/summary must resolve to the summary handler, not a 404 batch
    lookup — this pins the declaration-order requirement."""
    from starlette.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        res = client.get("/api/batches/summary")
        assert res.status_code == 200
        assert "awaiting_approval" in res.json()


@pytest.mark.asyncio
async def test_batch_items_include_latest_error_and_none_without_log():
    """Items in GET /api/batches/{id} expose error from their most
    recent failed log; items with no failed log get error=None."""
    from starlette.testclient import TestClient
    from app.main import app

    err_batch, err_item, _ = await _insert_batch_with_item_and_log(
        log_error="Notion API rejected the page create: database not shared",
    )
    clean_batch, clean_item, _ = await _insert_batch_with_item_and_log(
        log_error=None,
    )

    with TestClient(app) as client:
        err_res = client.get(f"/api/batches/{err_batch}")
        assert err_res.status_code == 200
        err_entry = next(t for t in err_res.json()["items"] if t["id"] == err_item)
        assert err_entry["error"] == (
            "Notion API rejected the page create: database not shared"
        )

        clean_res = client.get(f"/api/batches/{clean_batch}")
        assert clean_res.status_code == 200
        clean_entry = next(t for t in clean_res.json()["items"] if t["id"] == clean_item)
        assert clean_entry["error"] is None


@pytest.mark.asyncio
async def test_batch_item_error_picks_most_recent_log():
    """When an item has several failed logs, the newest executed_at wins."""
    from starlette.testclient import TestClient
    from app.main import app
    from app.db.models import ExecutionLogModel
    from app.db.session import async_session_factory

    batch_id, item_id, _ = await _insert_batch_with_item_and_log(
        log_error="first failure",
    )
    base = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        for offset_minutes, msg in ((5, "middle failure"), (10, "latest failure")):
            session.add(ExecutionLogModel(
                id=str(uuid.uuid4()),
                item_id=item_id,
                batch_id=batch_id,
                tool="notion",
                status="failed",
                idempotency_hash=uuid.uuid4().hex,
                item_description="",
                error=msg,
                executed_at=base + timedelta(minutes=offset_minutes),
            ))
        await session.commit()

    with TestClient(app) as client:
        res = client.get(f"/api/batches/{batch_id}")
        assert res.status_code == 200
        entry = next(t for t in res.json()["items"] if t["id"] == item_id)
        assert entry["error"] == "latest failure"


# ── History error exposure ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_history_log_dict_has_error_key():
    """GET /api/history log dicts carry the error column; a failed log
    shows its text and a fresh DB is at least keyed correctly."""
    from starlette.testclient import TestClient
    from app.main import app

    batch_id, item_id, _ = await _insert_batch_with_item_and_log(
        log_error="history surfacing probe failure",
    )

    with TestClient(app) as client:
        res = client.get("/api/history")
        assert res.status_code == 200
        history = res.json()
        entry = next(h for h in history if h["batch_id"] == batch_id)
        assert entry["logs"], "the inserted failed log must be present"
        log = entry["logs"][0]
        assert "error" in log
        assert log["error"] == "history surfacing probe failure"
        assert log["item_id"] == item_id


# ── Connector test-connection ────────────────────────────────────────


@pytest.mark.asyncio
async def test_connector_test_unknown_tool_is_400():
    from starlette.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        res = client.post("/api/connectors/test", json={"tool": "pipedream"})
        assert res.status_code == 400
        assert "Unknown tool" in res.json()["detail"]


@pytest.mark.asyncio
async def test_connector_test_task_ledger_always_succeeds():
    from starlette.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        res = client.post("/api/connectors/test", json={"tool": "task_ledger"})
        assert res.status_code == 200
        body = res.json()
        assert body["tool"] == "task_ledger"
        assert body["success"] is True
        assert body["detail"] == "Built-in — always available"


@pytest.mark.asyncio
async def test_connector_test_without_credential_is_false_then_true():
    """A vault tool with no stored token reports success=false with the
    no-credential detail; storing a runtime-generated uuid token (via the
    oauth/save endpoint, like phase 5) flips it to success=true."""
    from sqlalchemy import delete as _delete
    from starlette.testclient import TestClient
    from app.main import app
    from app.db.models import OAuthTokenModel
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        await session.execute(
            _delete(OAuthTokenModel).where(OAuthTokenModel.provider == "notion")
        )
        await session.commit()

    with TestClient(app) as client:
        before = client.post("/api/connectors/test", json={"tool": "notion"})
        assert before.status_code == 200
        before_body = before.json()
        assert before_body["tool"] == "notion"
        assert before_body["success"] is False
        assert before_body["detail"] == "No credential stored for this connector"
        # No secret material may ride along in the detail.
        assert "token" not in before_body["detail"].lower()

        # Positive case: store a runtime-generated (non-literal) token
        # through the real vault endpoint, then re-probe.
        saved = client.post(
            "/api/connectors/oauth/save",
            json={"provider": "notion", "access_token": _runtime_token()},
        )
        assert saved.status_code == 200

        after = client.post("/api/connectors/test", json={"tool": "notion"})
        assert after.status_code == 200
        after_body = after.json()
        assert after_body["success"] is True
        assert after_body["detail"] == "Credential found and connector ready"

    async with async_session_factory() as session:
        await session.execute(
            _delete(OAuthTokenModel).where(OAuthTokenModel.provider == "notion")
        )
        await session.commit()
