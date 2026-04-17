"""WCS access-control routes — profiles, admin, grants."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import text

from kaianolevine_api import auth as auth_mod
from kaianolevine_api.main import app


@pytest.fixture(autouse=True)
async def seed_dev_owner_wcs_admin(reset_db, async_engine) -> None:
    async with async_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO wcs_user_profiles (user_id, email, display_name, is_admin) "
                "VALUES ('dev-owner', '', '', 1) "
                "ON CONFLICT (user_id) DO UPDATE SET is_admin = excluded.is_admin"
            )
        )


@pytest.fixture
async def stranger_client(client):  # noqa: ARG001 — ensures DB override is active
    original_verify = auth_mod.verify_clerk_jwt
    auth_mod.verify_clerk_jwt = AsyncMock(return_value="stranger-user")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": "Bearer stranger-token"},
    ) as c:
        yield c
    auth_mod.verify_clerk_jwt = original_verify


async def test_wcs_me_get_returns_profile(client) -> None:
    r = await client.get("/v1/wcs/me")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["user_id"] == "dev-owner"
    assert d["is_admin"] is True


async def test_wcs_me_post_updates_fields(client) -> None:
    r = await client.post(
        "/v1/wcs/me",
        json={"email": "dj@example.com", "display_name": "DJ"},
    )
    assert r.status_code == 200
    g = await client.get("/v1/wcs/me")
    assert g.status_code == 200
    d = g.json()["data"]
    assert d["email"] == "dj@example.com"
    assert d["display_name"] == "DJ"


async def test_wcs_admin_list_users(client) -> None:
    r = await client.get("/v1/wcs/admin/users")
    assert r.status_code == 200
    users = r.json()["data"]
    assert any(u["user_id"] == "dev-owner" for u in users)


async def test_wcs_admin_grant_create_and_delete(client, async_engine) -> None:
    """Grant requires target user profile (FK)."""
    async with async_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO wcs_user_profiles (user_id, email, display_name, is_admin) "
                "VALUES ('grantee', 'g@example.com', 'Grantee', 0)"
            )
        )

    from tests.test_wcs_notes import (  # noqa: PLC0415
        _create_note,
        _create_transcript,
    )

    tr = await _create_transcript(client)
    note = await _create_note(client, tr["id"])
    nid = note["id"]

    r = await client.post(
        "/v1/wcs/admin/grants",
        json={"user_id": "grantee", "note_id": nid},
    )
    assert r.status_code == 201
    gid = r.json()["data"]["id"]

    lst = await client.get("/v1/wcs/admin/grants", params={"user_id": "grantee"})
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1

    d = await client.delete(f"/v1/wcs/admin/grants/{gid}")
    assert d.status_code == 204


async def test_wcs_admin_grant_duplicate_returns_409(client, async_engine) -> None:
    async with async_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO wcs_user_profiles (user_id, email, display_name, is_admin) "
                "VALUES ('g2', '', '', 0)"
            )
        )
    from tests.test_wcs_notes import _create_note, _create_transcript  # noqa: PLC0415

    tr = await _create_transcript(client)
    note = await _create_note(client, tr["id"])
    body = {"user_id": "g2", "note_id": note["id"]}
    assert (await client.post("/v1/wcs/admin/grants", json=body)).status_code == 201
    dup = await client.post("/v1/wcs/admin/grants", json=body)
    assert dup.status_code == 409


async def test_get_note_forbidden_for_stranger_without_grant(
    client, stranger_client, async_engine
) -> None:
    from tests.test_wcs_notes import _create_note, _create_transcript  # noqa: PLC0415

    tr = await _create_transcript(client)
    note = await _create_note(client, tr["id"])
    assert note["is_default_visible"] is False

    upsert = await stranger_client.post(
        "/v1/wcs/me", json={"email": "", "display_name": "S"}
    )
    assert upsert.status_code == 200

    r = await stranger_client.get(f"/v1/wcs/notes/{note['id']}")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


async def test_patch_default_visibility_admin(client) -> None:
    from tests.test_wcs_notes import _create_note, _create_transcript  # noqa: PLC0415

    tr = await _create_transcript(client)
    note = await _create_note(client, tr["id"])
    r = await client.patch(
        f"/v1/wcs/admin/notes/{note['id']}/visibility",
        json={"is_default_visible": True},
    )
    assert r.status_code == 200
    assert r.json()["data"]["is_default_visible"] is True
