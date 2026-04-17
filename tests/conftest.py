from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Ensure Settings() can be constructed during app import.
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)

# Contact form — dummy values so Settings validates cleanly in tests.
# Individual tests mock the actual HTTP calls to Turnstile and Brevo.
os.environ.setdefault("BREVO_API_KEY", "test-brevo-key")
os.environ.setdefault("CONTACT_TO_EMAIL", "to@example.com")
os.environ.setdefault("CONTACT_FROM_EMAIL", "from@example.com")
os.environ.setdefault("TURNSTILE_SECRET_KEY", "test-turnstile-secret")
os.environ.setdefault("CORS_ORIGINS", '["https://kaianolevine.com"]')

from kaianolevine_api import auth as auth_mod  # noqa: E402
from kaianolevine_api.config import get_settings  # noqa: E402
from kaianolevine_api.database import get_db_session  # noqa: E402
from kaianolevine_api.main import app  # noqa: E402
from kaianolevine_api.models import Base  # noqa: E402


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
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
async def reset_db(async_engine) -> AsyncIterator[None]:
    async with async_engine.begin() as conn:
        # Delete in reverse dependency order to avoid FK violations.
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield


@pytest.fixture
async def client(async_engine) -> AsyncIterator[httpx.AsyncClient]:
    sessionmaker = async_sessionmaker(
        async_engine, expire_on_commit=False, autoflush=False
    )

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    original_verify = auth_mod.verify_clerk_jwt
    auth_mod.verify_clerk_jwt = AsyncMock(return_value="dev-owner")

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": "Bearer test-token"},
    ) as client:
        yield client

    app.dependency_overrides.pop(get_db_session, None)
    auth_mod.verify_clerk_jwt = original_verify
