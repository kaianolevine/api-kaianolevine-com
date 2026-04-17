"""Authentication — Clerk JWT verification tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from kaianolevine_api import auth as auth_mod
from kaianolevine_api.auth import get_current_owner, verify_clerk_jwt


class _SettingsShim:
    """Minimal settings object for unit-testing auth helpers."""
    CLERK_JWKS_URL = "https://example.clerk.accounts.dev/.well-known/jwks.json"
    CLERK_ISSUER = "https://example.clerk.accounts.dev"


@pytest.mark.asyncio
async def test_valid_jwt_returns_sub(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_verify(token: str, settings: object) -> str | None:
        del settings
        return "user_123" if token == "good" else None

    monkeypatch.setattr(auth_mod, "verify_clerk_jwt", fake_verify)

    owner = await get_current_owner(
        authorization="Bearer good",
        settings=_SettingsShim(),  # type: ignore[arg-type]
    )
    assert owner == "user_123"


@pytest.mark.asyncio
async def test_missing_authorization_raises_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_mod, "verify_clerk_jwt", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as excinfo:
        await get_current_owner(
            authorization=None,
            settings=_SettingsShim(),  # type: ignore[arg-type]
        )
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_raises_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_mod, "verify_clerk_jwt", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as excinfo:
        await get_current_owner(
            authorization="Bearer bad",
            settings=_SettingsShim(),  # type: ignore[arg-type]
        )
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_clerk_jwt_returns_none_without_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Empty:
        CLERK_JWKS_URL = None
        CLERK_ISSUER = None

    fetch = AsyncMock(side_effect=AssertionError("JWKS must not be fetched"))
    monkeypatch.setattr(auth_mod, "_fetch_jwks_document", fetch)

    sub = await verify_clerk_jwt("any", _Empty())  # type: ignore[arg-type]
    assert sub is None
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_flags_list_accessible(client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Integration: flags endpoint still accessible after auth cleanup."""
    monkeypatch.setattr(auth_mod, "verify_clerk_jwt", AsyncMock(return_value="dev-owner"))
    r = await client.get("/v1/flags", headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200
