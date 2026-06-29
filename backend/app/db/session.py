"""
Async SQLAlchemy engine + session management.

The backend is stateless across replicas; all shared state lives here in
Postgres (and in Qdrant/S3). We use the async engine (asyncpg driver) so FastAPI
request handlers can `await` DB calls without blocking the event loop.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# echo=False in production; flip to True locally to see emitted SQL.
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # let objects stay usable after commit in handlers
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a session, ensures it's closed."""
    async with AsyncSessionLocal() as session:
        yield session
