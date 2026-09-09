"""Auth adapters — this service as a conformant identity enforcement point.

Credential verification itself is not tested here any more: it moved to the
`identity` package and is tested against that package's fixture suite. What
these cover is what remains this service's responsibility — turning a
verified subject into a FastAPI dependency result, and running the four
contract functions in the right order with the right side effects.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from identity.errors import CredentialInvalid
from identity.store import (
    ExplicitGrant,
    Issuer,
    Principal,
    PrincipalRole,
    Role,
    RoleScope,
)
from identity.store.models import AuditEventRow
from identity.types import VerifiedSubject
from sqlalchemy import select

from kaianolevine_api import auth as auth_mod
from kaianolevine_api.auth import (
    get_current_owner,
    require_scope,
    verify_bearer,
)

ISSUER = "https://clerk.kaianolevine.com"


class _SettingsShim:
    CLERK_JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
    CLERK_ISSUER = ISSUER
    CLERK_ISSUERS = None


def _subject(sub: str, kind: str = "human") -> VerifiedSubject:
    return VerifiedSubject(issuer=ISSUER, subject=sub, kind=kind)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# verify_bearer — the 401/503 boundary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_authorization_raises_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await verify_bearer(None, _SettingsShim())  # type: ignore[arg-type]
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_non_bearer_scheme_raises_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await verify_bearer("Basic abc123", _SettingsShim())  # type: ignore[arg-type]
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_unconfigured_service_rejects_rather_than_admits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No configured issuer must fail closed, not open."""

    class _Empty:
        CLERK_JWKS_URL = None
        CLERK_ISSUER = None
        CLERK_ISSUERS = None

    with pytest.raises(HTTPException) as exc:
        await verify_bearer("Bearer anything", _Empty())  # type: ignore[arg-type]
    assert exc.value.status_code == 401


def _verifier_raising(exc: Exception) -> object:
    class _Verifier:
        verify = AsyncMock(side_effect=exc)

    return _Verifier()


@pytest.mark.asyncio
async def test_credential_failure_still_raises_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The credential was judged and found bad — that is still a 401."""
    monkeypatch.setattr(
        auth_mod,
        "get_verifier",
        lambda settings=None: _verifier_raising(CredentialInvalid("bad signature")),
    )
    with pytest.raises(HTTPException) as exc:
        await verify_bearer("Bearer token", _SettingsShim())  # type: ignore[arg-type]
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_unreachable_issuer_raises_503_not_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A JWKS fetch that never connects leaves the credential unjudged.

    401 would tell the caller their session is invalid, and a client that
    believes it logs them out over an outage that self-heals.
    """
    monkeypatch.setattr(
        auth_mod,
        "get_verifier",
        lambda settings=None: _verifier_raising(
            httpx.ConnectError("All connection attempts failed")
        ),
    )
    with pytest.raises(HTTPException) as exc:
        await verify_bearer("Bearer token", _SettingsShim())  # type: ignore[arg-type]
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "auth_unavailable"


@pytest.mark.asyncio
async def test_issuer_timeout_raises_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every httpx transport failure maps the same way, not just ConnectError."""
    monkeypatch.setattr(
        auth_mod,
        "get_verifier",
        lambda settings=None: _verifier_raising(httpx.ReadTimeout("timed out")),
    )
    with pytest.raises(HTTPException) as exc:
        await verify_bearer("Bearer token", _SettingsShim())  # type: ignore[arg-type]
    assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# get_current_owner — retained only for /v1/wcs/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_owner_returns_issuer_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_mod, "verify_bearer", AsyncMock(return_value=_subject("user_123"))
    )
    owner = await get_current_owner(
        authorization="Bearer good",
        settings=_SettingsShim(),  # type: ignore[arg-type]
    )
    assert owner == "user_123"


# ---------------------------------------------------------------------------
# require_scope — all four contract functions
# ---------------------------------------------------------------------------


async def _seed_principal(session, *, subject: str, roles: list[str]) -> uuid.UUID:
    session.add(Issuer(issuer=ISSUER, jwks_url=f"{ISSUER}/.well-known/jwks.json"))
    session.add(Role(name="catalog-ingest", description="ingest"))
    session.add(RoleScope(role_name="catalog-ingest", scope="catalog.sets.write"))
    session.add(Role(name="wcs-reader", description="read"))
    session.add(RoleScope(role_name="wcs-reader", scope="wcs.notes.read"))
    await session.flush()

    pid = uuid.uuid4()
    session.add(Principal(id=pid, kind="machine", issuer=ISSUER, subject=subject))
    for r in roles:
        session.add(PrincipalRole(principal_id=pid, role_name=r))
    await session.commit()
    return pid


class _Req:
    """Minimal stand-in for starlette's Request."""

    def __init__(self, path_params: dict | None = None) -> None:
        self.path_params = path_params or {}
        self.headers: dict[str, str] = {}


@pytest.mark.asyncio
async def test_require_scope_allows_and_audits(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed_principal(
        db_session, subject="mch_deejay_cog", roles=["catalog-ingest"]
    )
    monkeypatch.setattr(
        auth_mod,
        "verify_bearer",
        AsyncMock(return_value=_subject("mch_deejay_cog", "machine")),
    )

    dep = require_scope("catalog.sets.write")
    principal = await dep(
        _Req(),  # type: ignore[arg-type]
        authorization="Bearer good",
        settings=_SettingsShim(),  # type: ignore[arg-type]
        session=db_session,
    )
    assert principal.id == pid

    rows = (await db_session.execute(select(AuditEventRow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].allowed is True
    assert rows[0].reason == "granted_by_role"
    assert rows[0].enforcement_point == "api-kaianolevine-com"


@pytest.mark.asyncio
async def test_require_scope_denies_and_still_audits(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A denial must reach the trail. This is the case Keystone never had."""
    await _seed_principal(db_session, subject="mch_deejay_cog", roles=["wcs-reader"])
    monkeypatch.setattr(
        auth_mod,
        "verify_bearer",
        AsyncMock(return_value=_subject("mch_deejay_cog", "machine")),
    )

    dep = require_scope("catalog.sets.write")
    with pytest.raises(HTTPException) as exc:
        await dep(
            _Req(),  # type: ignore[arg-type]
            authorization="Bearer good",
            settings=_SettingsShim(),  # type: ignore[arg-type]
            session=db_session,
        )
    assert exc.value.status_code == 403

    rows = (await db_session.execute(select(AuditEventRow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].allowed is False
    assert rows[0].reason == "no_matching_scope"


@pytest.mark.asyncio
async def test_unknown_principal_is_403_not_401(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid credential this ecosystem has never seen is authenticated but
    unknown — a 401 would tell the caller their token was bad, which is false."""
    monkeypatch.setattr(
        auth_mod,
        "verify_bearer",
        AsyncMock(return_value=_subject("mch_never_seen", "machine")),
    )
    dep = require_scope("catalog.sets.write")
    with pytest.raises(HTTPException) as exc:
        await dep(
            _Req(),  # type: ignore[arg-type]
            authorization="Bearer good",
            settings=_SettingsShim(),  # type: ignore[arg-type]
            session=db_session,
        )
    assert exc.value.status_code == 403

    rows = (await db_session.execute(select(AuditEventRow))).scalars().all()
    assert rows[0].reason == "principal_not_found"
    assert rows[0].subject == "mch_never_seen"


@pytest.mark.asyncio
async def test_explicit_grant_satisfies_resource_scoped_endpoint(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed_principal(db_session, subject="user_x", roles=[])
    db_session.add(
        ExplicitGrant(principal_id=pid, scope="wcs.notes.read", resource="note-42")
    )
    await db_session.commit()

    monkeypatch.setattr(
        auth_mod, "verify_bearer", AsyncMock(return_value=_subject("user_x"))
    )
    dep = require_scope("wcs.notes.read", resource_param="note_id")
    principal = await dep(
        _Req({"note_id": "note-42"}),  # type: ignore[arg-type]
        authorization="Bearer good",
        settings=_SettingsShim(),  # type: ignore[arg-type]
        session=db_session,
    )
    assert principal.id == pid

    rows = (await db_session.execute(select(AuditEventRow))).scalars().all()
    assert rows[0].reason == "granted_by_explicit_grant"
    assert rows[0].resource == "note-42"


@pytest.mark.asyncio
async def test_flags_list_accessible(client) -> None:
    """Integration: the routers that use the legacy dependency still work."""
    r = await client.get("/v1/flags", headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200
