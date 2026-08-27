"""Pytest configuration and session fixtures for Kairos test suite."""
import pytest
import asyncio
from sqlalchemy import text
from app.db.session import engine, init_db


@pytest.fixture(scope="session", autouse=True)
def setup_and_teardown_test_db():
    """Initializes schema before test session and cleanly purges all test data on finish."""
    async def _init():
        await init_db()

    async def _cleanup():
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE execution_logs CASCADE;"))
            await conn.execute(text("TRUNCATE TABLE action_items CASCADE;"))
            await conn.execute(text("TRUNCATE TABLE batches CASCADE;"))
            await conn.execute(text("TRUNCATE TABLE oauth_tokens CASCADE;"))
            await conn.execute(text("TRUNCATE TABLE routing_feedback CASCADE;"))
            await conn.execute(text("TRUNCATE TABLE task_ledger_tasks CASCADE;"))

    asyncio.run(_init())
    yield
    asyncio.run(_cleanup())
