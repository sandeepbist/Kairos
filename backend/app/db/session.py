"""Database connection, pooling, and session lifecycle management."""
import logging
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from app.config import settings
from .models import Base

logger = logging.getLogger(__name__)

# Engine configured for async PostgreSQL via asyncpg.
# NullPool in test to prevent event loop connection detachment across pytest
# runs; AsyncAdaptedQueuePool with explicit bounds otherwise.
use_null_pool = settings.APP_ENV == "test"

_pool_kwargs: dict = {"pool_pre_ping": True, "pool_recycle": 1800}
if not use_null_pool:
    # Production pool bounds: small API, one operator, bursty dashboard polls.
    _pool_kwargs.update(
        pool_size=10 if settings.is_production else 5,
        max_overflow=20 if settings.is_production else 10,
        pool_timeout=30,
    )

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool if use_null_pool else AsyncAdaptedQueuePool,
    connect_args={
        "server_settings": {"application_name": "kairos-api"},
        # Terminate queries stuck on locks rather than hanging the pool.
        "timeout": 15,
        "command_timeout": 60,
    },
    **_pool_kwargs,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing async database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Verifies database connectivity and schema readiness.

    Schema ownership lives with Alembic migrations; this function must
    never mutate the schema (create_all drifted silently from migrations).
    It checks that the expected tables exist and fails fast with an
    actionable message if migrations have not been applied.
    """
    async with engine.connect() as conn:
        # pgvector is optional; request it but tolerate its absence.
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.commit()
        except Exception:
            await conn.rollback()

        result = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename = 'batches'"
            )
        )
        if result.scalar() is None:
            raise RuntimeError(
                "Database schema is not initialized. Run migrations first: "
                "'alembic upgrade head' from the backend directory. "
                "Refusing to start with a missing schema."
            )
        logger.debug("Database schema verified (batches table present).")


# Retained for tooling that inspects metadata (e.g., alembic autogenerate).
Base = Base
