"""Core basics: version fallback, dev-key validity, JSON log shape,
session cleanup on endpoint errors, and the JSON 404 contract."""
import logging

import pytest


def test_get_app_version_matches_version_file_or_fallback():
    from app.config import get_app_version

    assert isinstance(get_app_version(), str) and get_app_version()


def test_dev_encryption_key_is_valid_fernet():
    from cryptography.fernet import Fernet

    from app.config import _generate_dev_encryption_key

    Fernet(_generate_dev_encryption_key().encode())


def test_json_formatter_emits_ts_level_msg():
    from app.core.logging import JsonFormatter

    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello", args=(), exc_info=None,
    )
    import json

    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["ts"] and payload["logger"] == "t"


@pytest.mark.asyncio
async def test_get_db_rolls_back_and_closes_on_error():
    from app.db.session import get_db

    agen = get_db()
    session = await agen.asend(None)
    with pytest.raises(RuntimeError):
        await agen.athrow(RuntimeError("boom"))
    assert not session.in_transaction()


def test_unknown_route_returns_json_404():
    from starlette.testclient import TestClient

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        res = client.get("/api/does-not-exist")
        assert res.status_code == 404
        assert res.json() == {"detail": "Resource not found."}


@pytest.mark.asyncio
async def test_run_worker_retries_and_respects_cancel(monkeypatch):
    """A dead Temporal server must not kill the worker process: it backs
    off and retries, while cancellation still propagates on shutdown."""
    import asyncio as _asyncio

    import app.temporal.worker as _worker

    calls = 0

    async def _dead():
        nonlocal calls
        calls += 1
        raise ConnectionError("temporal down")

    monkeypatch.setattr(_worker, "get_temporal_client", _dead)
    with pytest.raises(TimeoutError):
        await _asyncio.wait_for(_worker.run_worker(), timeout=2.5)
    assert calls >= 2

    task = _asyncio.create_task(_worker.run_worker())
    await _asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(_asyncio.CancelledError):
        await task
