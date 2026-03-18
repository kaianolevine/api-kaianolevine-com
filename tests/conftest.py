from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Ensure Settings() can be constructed during app import.
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)

from deejay_sets_api.database import get_db_session  # noqa: E402
from deejay_sets_api.main import app  # noqa: E402
from deejay_sets_api.models import Base  # noqa: E402


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def async_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
async def create_tables(async_engine) -> AsyncIterator[None]:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True)
async def reset_db(async_engine) -> AsyncIterator[None]:
    async with async_engine.begin() as conn:
        # Delete in reverse dependency order to avoid FK violations.
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield


@pytest.fixture
async def client(async_engine) -> AsyncIterator[httpx.AsyncClient]:
    sessionmaker = async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.pop(get_db_session, None)
