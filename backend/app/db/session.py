"""Database connection and session lifecycle management."""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from sqlalchemy import text
from app.config import settings
from .models import Base

# Engine configured for async PostgreSQL via asyncpg
# Use NullPool in test/dev to prevent event loop connection detachment across pytest runs
pool_class = NullPool if settings.APP_ENV == "test" else AsyncAdaptedQueuePool

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    poolclass=pool_class,
    pool_pre_ping=True,
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
    """Initialize database tables and extensions."""
    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        except Exception:
            pass  # pgvector optional if running standard Postgres
        await conn.run_sync(Base.metadata.create_all)
