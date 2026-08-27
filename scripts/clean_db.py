#!/usr/bin/env python3
"""Pristine database cleanup script: purges all test data and leftover tokens."""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db.session import engine
from sqlalchemy import text


async def clean_database():
    print("🧹 Cleaning database tables...")
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE execution_logs CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE action_items CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE batches CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE oauth_tokens CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE routing_feedback CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE task_ledger_tasks CASCADE;"))
    print("✓ All tables truncated cleanly. Database is in a pristine state.")

if __name__ == "__main__":
    asyncio.run(clean_database())
