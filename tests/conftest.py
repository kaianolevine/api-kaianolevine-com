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

# Discord notifications — a dummy webhook and secret so Settings validates.
# The notification tests mock the Discord call itself with respx.
os.environ.setdefault(
    "DISCORD_WEBHOOK_URL", "https://discord.test/api/webhooks/1/token"
)
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-github-secret")

from identity.store import (  # noqa: E402
    IdentityBase,
    Issuer,
    Principal,
    PrincipalRole,
    Role,
    RoleScope,
)
from identity.types import VerifiedSubject  # noqa: E402

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
        # The identity principal store has its own declarative base rather
        # than grafting itself onto this app's. Creating it is one explicit
        # extra line, which is the intended trade.
        await conn.run_sync(IdentityBase.metadata.create_all)
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
        for table in reversed(IdentityBase.metadata.sorted_tables):
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

    # Stub step 1 of the contract only. Verification is identity's
    # responsibility and is tested there; these tests are about this
    # service's adapters and its routers.
    original_verify = auth_mod.verify_bearer
    auth_mod.verify_bearer = AsyncMock(
        return_value=VerifiedSubject(
            issuer="https://clerk.kaianolevine.com",
            subject="dev-owner",
            kind="human",
        )
    )

    async with sessionmaker() as seed_session:
        await seed_identity(seed_session)

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": "Bearer test-token"},
    ) as client:
        yield client

    app.dependency_overrides.pop(get_db_session, None)
    auth_mod.verify_bearer = original_verify


@pytest.fixture
async def db_session(async_engine) -> AsyncIterator[AsyncSession]:
    """A bare session for tests that seed or inspect tables directly."""
    maker = async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        yield session


# The default test caller. Router tests exercise endpoints, not the principal
# store, so the caller they authenticate as needs to already exist and hold
# the scopes those endpoints require — the same state a real caller reaches by
# registering once. Tests that care about an *unknown* caller use a different
# subject and are unaffected.
DEV_ISSUER = "https://clerk.kaianolevine.com"
DEV_SUBJECT = "dev-owner"

_DEV_ROLES = {
    "wcs-admin": [
        "wcs.notes.read",
        "wcs.notes.write",
        "wcs.grants.write",
        "wcs.sources.write",
        "wcs.transcripts.write",
        "wcs.embeddings.write",
        "config.flags.write",
        "wcs.corpus.read",
    ],
    "wcs-reader": ["wcs.notes.read"],
    "corpus-reader": ["wcs.notes.read", "wcs.corpus.read"],
    "pipeline-writer": ["pipeline.evaluations.write", "pipeline.findings.write"],
    "catalog-ingest": [
        "catalog.sets.write",
        "catalog.tracks.write",
        "catalog.plays.write",
    ],
    "wcs-writer": [
        "wcs.notes.read",
        "wcs.notes.write",
        "wcs.sources.write",
        "wcs.transcripts.write",
    ],
    "notifier": ["notify.messages.send"],
}


async def seed_identity(session: AsyncSession) -> None:
    """Idempotently create the issuer, role vocabulary and default principal."""
    from sqlalchemy import select

    if (
        await session.execute(select(Issuer).where(Issuer.issuer == DEV_ISSUER))
    ).scalars().first() is None:
        session.add(
            Issuer(
                issuer=DEV_ISSUER,
                jwks_url=f"{DEV_ISSUER}/.well-known/jwks.json",
            )
        )
    # Machines authenticate with named keys, not through an issuer with a JWKS.
    if (
        await session.execute(select(Issuer).where(Issuer.issuer == "apikey"))
    ).scalars().first() is None:
        session.add(Issuer(issuer="apikey", jwks_url=None))
    for name, scopes in _DEV_ROLES.items():
        if (
            await session.execute(select(Role).where(Role.name == name))
        ).scalars().first() is None:
            session.add(Role(name=name, description=name))
            for scope in scopes:
                session.add(RoleScope(role_name=name, scope=scope))
    await session.flush()

    principal = (
        (
            await session.execute(
                select(Principal).where(
                    Principal.issuer == DEV_ISSUER, Principal.subject == DEV_SUBJECT
                )
            )
        )
        .scalars()
        .first()
    )
    if principal is None:
        principal = Principal(
            kind="human",
            issuer=DEV_ISSUER,
            subject=DEV_SUBJECT,
            display_name="dev-owner",
        )
        session.add(principal)
        await session.flush()
        for name in _DEV_ROLES:
            session.add(
                PrincipalRole(
                    principal_id=principal.id, role_name=name, granted_by="conftest"
                )
            )
    await session.commit()
