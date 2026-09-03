"""Pytest configuration and session fixtures for Kairos test suite."""
import asyncio
import os
import subprocess
import sys

import pytest
from sqlalchemy import text

from app.db.session import engine

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")


@pytest.fixture(autouse=True)
def reset_rate_limit_windows():
    """Clears the app's in-memory rate-limit windows around every test.

    The middleware instances live on the shared FastAPI app object, so
    burst tests (which legitimately exhaust the limits) would otherwise
    throttle unrelated suites that happen to share the process.
    """
    from app.core.ratelimit import RateLimitMiddleware

    RateLimitMiddleware.reset_for_tests()
    yield
    RateLimitMiddleware.reset_for_tests()


@pytest.fixture(scope="session", autouse=True)
def setup_and_teardown_test_db():
    """Applies migrations once per session, purges test data on finish."""

    def _migrate_to_head():
        # Alembic's env.py calls asyncio.run internally, which cannot nest
        # inside pytest's running loop — run it as a subprocess.
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=True,
            cwd=_BACKEND_DIR,
            env={**os.environ, "PYTHONPATH": _BACKEND_DIR},
        )

    def _cleanup_tables():
        async def _purge():
            async with engine.begin() as conn:
                for table in (
                    "execution_logs",
                    "action_items",
                    "batches",
                    "oauth_tokens",
                    "routing_feedback",
                    "task_ledger_tasks",
                    "webhook_deliveries",
                    "webhook_endpoints",
                ):
                    await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))

        asyncio.run(_purge())

    _migrate_to_head()
    yield
    _cleanup_tables()
