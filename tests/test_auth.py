from __future__ import annotations

import jwt
import pytest

from deejay_sets_api import auth as auth_module
from deejay_sets_api.config import get_settings


def _set_auth_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool,
    jwks_url: str = "https://clerk.example/.well-known/jwks.json",
) -> None:
    monkeypatch.setenv("CLERK_AUTH_ENABLED", "true" if enabled else "false")
    monkeypatch.setenv("CLERK_JWKS_URL", jwks_url)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_protected_endpoint_allows_requests_without_auth_when_disabled(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_auth_env(monkeypatch, enabled=False)

    response = await client.get("/v1/flags", headers={})

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_protected_endpoint_requires_authorization_header_when_enabled(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_auth_env(monkeypatch, enabled=True)

    response = await client.get("/v1/flags", headers={})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_rejects_malformed_token_when_enabled(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_auth_env(monkeypatch, enabled=True)

    async def _fake_get_jwks_key(_: str):
        return "fake-public-key"

    monkeypatch.setattr(auth_module, "get_jwks_key", _fake_get_jwks_key)

    response = await client.get(
        "/v1/flags",
        headers={"Authorization": "Bearer malformed.token.value"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_accepts_valid_token_when_enabled(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_auth_env(monkeypatch, enabled=True)

    async def _fake_get_jwks_key(_: str):
        return "fake-public-key"

    def _fake_decode(token: str, key: str, algorithms: list[str]):
        assert token == "valid-token"
        assert key == "fake-public-key"
        assert algorithms == ["RS256"]
        return {"sub": "owner-from-token"}

    monkeypatch.setattr(auth_module, "get_jwks_key", _fake_get_jwks_key)
    monkeypatch.setattr(jwt, "decode", _fake_decode)

    response = await client.get(
        "/v1/flags",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
