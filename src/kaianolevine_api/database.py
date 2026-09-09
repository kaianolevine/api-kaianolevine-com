from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from .config import Settings, get_settings


@lru_cache(maxsize=1)
def _get_engine(database_url: str):
    # Ensure async driver is used with SQLAlchemy async engine.
    # If the URL comes in as `postgresql://...` (psycopg2 default), SQLAlchemy
    # will attempt to import psycopg2 (not installed in this project).
    if database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgres://") and "+asyncpg" not in database_url:
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)

    # SQLite in-memory DB needs a StaticPool to share the same connection across sessions.
    connect_args = {}
    poolclass = None
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        poolclass = StaticPool

    return create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        # Keeps bound parameters out of every DBAPI exception's string
        # form, which is what anything rendering that exception — a log
        # line, a traceback, a notification — would otherwise carry.
        hide_parameters=True,
        connect_args=connect_args,
        poolclass=poolclass,
    )


def get_engine(settings: Settings | None = None):
    """TODO: describe this function."""
    settings = settings or get_settings()
    return _get_engine(settings.DATABASE_URL)


@lru_cache(maxsize=1)
def get_sessionmaker(database_url: str):
    """Return the module-level async sessionmaker, creating it on first use."""
    engine = _get_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session for a request lifecycle."""
    settings = get_settings()
    sessionmaker = get_sessionmaker(settings.DATABASE_URL)
    async with sessionmaker() as session:
        yield session
