"""Reconciliation guardrails — what a deploy may and may not change.

The declaration is the source of truth for machines, so a deploy is what
applies it. These cover the limits on that power: it touches machines only,
grants it made itself only, and refuses anything it cannot verify.
"""

from __future__ import annotations

import uuid

import pytest
from identity.apikey import API_KEY_ISSUER
from identity.store import Principal, PrincipalRole
from sqlalchemy import select

from kaianolevine_api import identity_registry as reg
from kaianolevine_api import main as main_mod
from kaianolevine_api.services import discord
from tests.conftest import DEV_ISSUER, seed_identity


async def _roles_of(session, subject: str, issuer: str = API_KEY_ISSUER) -> set[str]:
    row = (
        (
            await session.execute(
                select(Principal).where(
                    Principal.issuer == issuer, Principal.subject == subject
                )
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        return set()
    return set(
        (
            await session.execute(
                select(PrincipalRole.role_name).where(
                    PrincipalRole.principal_id == row.id
                )
            )
        )
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_removing_a_role_from_the_file_revokes_it(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revocation is a code change — that is the point of declaring it."""
    await seed_identity(db_session)
    monkeypatch.setattr(
        reg,
        "MACHINES",
        (reg.Machine(name="deejay-cog", roles=("catalog-ingest", "pipeline-writer")),),
    )
    await reg.reconcile(db_session)
    assert await _roles_of(db_session, "deejay-cog") == {
        "catalog-ingest",
        "pipeline-writer",
    }

    monkeypatch.setattr(
        reg, "MACHINES", (reg.Machine(name="deejay-cog", roles=("catalog-ingest",)),)
    )
    assert (await reg.reconcile(db_session))["revoked"] == 1
    assert await _roles_of(db_session, "deejay-cog") == {"catalog-ingest"}


@pytest.mark.asyncio
async def test_hand_granted_roles_are_left_alone(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A one-off grant must survive an unrelated deploy.

    Reconciliation removes only rows it wrote, identified by granted_by.
    """
    await seed_identity(db_session)
    pid = uuid.uuid4()
    db_session.add(
        Principal(
            id=pid,
            kind="machine",
            issuer=API_KEY_ISSUER,
            subject="manual-cog",
            display_name="manual-cog",
        )
    )
    db_session.add(
        PrincipalRole(
            principal_id=pid, role_name="pipeline-writer", granted_by="a-human"
        )
    )
    await db_session.commit()

    monkeypatch.setattr(reg, "MACHINES", ())
    assert (await reg.reconcile(db_session))["revoked"] == 0
    assert await _roles_of(db_session, "manual-cog") == {"pipeline-writer"}


@pytest.mark.asyncio
async def test_human_principals_are_never_touched(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A code deploy must not re-grant or revoke a person's access."""
    await seed_identity(db_session)
    pid = uuid.uuid4()
    db_session.add(Principal(id=pid, kind="human", issuer=DEV_ISSUER, subject="user_2"))
    db_session.add(
        PrincipalRole(
            principal_id=pid, role_name="catalog-ingest", granted_by=reg.GRANTED_BY
        )
    )
    await db_session.commit()

    monkeypatch.setattr(reg, "MACHINES", ())
    assert (await reg.reconcile(db_session))["revoked"] == 0
    assert await _roles_of(db_session, "user_2", DEV_ISSUER) == {"catalog-ingest"}


@pytest.mark.asyncio
async def test_unknown_role_is_refused_not_invented(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A typo must not mint a role that grants nothing and looks correct.

    The machine is skipped entirely rather than created with no roles, so the
    error surfaces as an absent principal rather than a silent denial later.
    """
    await seed_identity(db_session)
    monkeypatch.setattr(
        reg, "MACHINES", (reg.Machine(name="oops", roles=("catalog-injest",)),)
    )
    assert await reg.reconcile(db_session) == {
        "created": 0,
        "granted": 0,
        "revoked": 0,
    }
    assert await _roles_of(db_session, "oops") == set()


@pytest.mark.asyncio
async def test_reconcile_failure_reports_and_still_boots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The service must come up; the failure must not be silent.

    Swallowing this is fail-closed for grants and wide open for revocations:
    a decommissioned machine keeps its scopes and the deploy still reports
    success, so the failure has to leave the process to be found at all.
    """
    sent: list[dict] = []

    async def _explode(_session) -> dict[str, int]:
        raise RuntimeError("connection reset during reconcile")

    async def _capture(*, settings, payload) -> bool:
        sent.append(payload)
        return True

    monkeypatch.setattr(reg, "reconcile", _explode)
    monkeypatch.setattr(discord, "send_message", _capture)

    async with main_mod.lifespan(main_mod.app):
        pass

    assert len(sent) == 1, "a failed reconcile must reach the channel"
    embed = sent[0]["embeds"][0]
    assert "RuntimeError" in embed["description"]
    assert "revocation" in embed["description"]


@pytest.mark.asyncio
async def test_reconcile_failure_message_carries_no_row_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reconcile embed obeys the same rule as the middleware."""
    from sqlalchemy.exc import IntegrityError

    sent: list[dict] = []

    async def _explode(_session) -> dict[str, int]:
        raise IntegrityError(
            "INSERT INTO identity_principals (subject) VALUES (?)",
            ("Kristen Wallace — private lesson notes",),
            Exception("UNIQUE constraint failed"),
        )

    async def _capture(*, settings, payload) -> bool:
        sent.append(payload)
        return True

    monkeypatch.setattr(reg, "reconcile", _explode)
    monkeypatch.setattr(discord, "send_message", _capture)

    async with main_mod.lifespan(main_mod.app):
        pass

    assert len(sent) == 1
    description = sent[0]["embeds"][0]["description"]
    assert "IntegrityError" in description
    assert "Kristen Wallace" not in description
    assert "INSERT INTO" not in description


@pytest.mark.asyncio
async def test_reconcile_failure_survives_a_dead_discord(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reporting the failure must not become a second way to fail startup."""

    async def _explode(_session) -> dict[str, int]:
        raise RuntimeError("connection reset during reconcile")

    async def _also_explode(*, settings, payload) -> bool:
        raise RuntimeError("discord is down too")

    monkeypatch.setattr(reg, "reconcile", _explode)
    monkeypatch.setattr(discord, "send_message", _also_explode)

    async with main_mod.lifespan(main_mod.app):
        pass


def test_declared_lookup() -> None:
    assert reg.declared("deejay-cog") is not None
    assert reg.declared("no-such-cog") is None
