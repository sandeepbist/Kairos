"""Pytest configuration and session fixtures for Kairos test suite."""
import asyncio
import os
import subprocess
import sys

import pytest
from sqlalchemy import text

from app.db.session import engine

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")


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
                ):
                    await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))

        asyncio.run(_purge())

    _migrate_to_head()
    yield
    _cleanup_tables()
