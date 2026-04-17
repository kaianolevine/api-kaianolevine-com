"""Tests for WCS notes endpoints — contract, happy path, failure paths, output shape."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
async def seed_dev_owner_wcs_admin(reset_db, async_engine) -> None:
    """X-Owner-Id dev-owner can see all notes via WCS admin flag (matches test cog identity)."""
    async with async_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO wcs_user_profiles (user_id, email, display_name, is_admin) "
                "VALUES ('dev-owner', '', '', 1) "
                "ON CONFLICT (user_id) DO UPDATE SET is_admin = excluded.is_admin"
            )
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _transcript_payload(**overrides) -> dict:
    base = {
        "raw_text": "Instructor said: keep your frame and stay on axis.",
        "source_type": "plaud",
        "source_filename": "2026-04-01 Kaiano > Sarah - Frame.txt",
        "drive_file_id": "drive-file-abc123",
    }
    return {**base, **overrides}


def _note_payload(transcript_id: str, **overrides) -> dict:
    base = {
        "transcript_id": transcript_id,
        "title": "Frame and axis — private lesson",
        "session_date": "2024-01-15",
        "session_type": "private_lesson",
        "instructors": ["Kaiano"],
        "students": ["Sarah"],
        "organization": "",
        "visibility": "private",
        "model": "claude-sonnet-4-6",
        "provider": "anthropic",
        "notes_json": {
            "title": "Frame and axis",
            "summary": "Worked on frame stability and staying on axis.",
            "key_concepts": ["frame", "axis"],
        },
    }
    return {**base, **overrides}


async def _create_transcript(client, **overrides) -> dict:
    resp = await client.post(
        "/v1/wcs/transcripts", json=_transcript_payload(**overrides)
    )
    assert resp.status_code == 200
    return resp.json()["data"]


async def _create_note(client, transcript_id: str, **overrides) -> dict:
    resp = await client.post(
        "/v1/wcs/notes", json=_note_payload(transcript_id, **overrides)
    )
    assert resp.status_code == 200
    return resp.json()["data"]


# ── POST /v1/wcs/transcripts ──────────────────────────────────────────────────


async def test_create_transcript_returns_envelope(client) -> None:
    resp = await client.post("/v1/wcs/transcripts", json=_transcript_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data", "meta"}
    assert body["meta"]["count"] == 1


async def test_create_transcript_output_shape(client) -> None:
    resp = await client.post("/v1/wcs/transcripts", json=_transcript_payload())
    data = resp.json()["data"]
    assert "id" in data
    assert "created_at" in data
    assert data["source_type"] == "plaud"
    assert data["source_filename"] == "2026-04-01 Kaiano > Sarah - Frame.txt"
    assert data["drive_file_id"] == "drive-file-abc123"


async def test_create_transcript_validation_error(client) -> None:
    resp = await client.post("/v1/wcs/transcripts", json={"source_type": "plaud"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_create_transcript_invalid_source_type(client) -> None:
    resp = await client.post(
        "/v1/wcs/transcripts",
        json=_transcript_payload(source_type="cassette_tape"),
    )
    assert resp.status_code == 422


# ── POST /v1/wcs/notes ────────────────────────────────────────────────────────


async def test_create_note_happy_path(client) -> None:
    transcript = await _create_transcript(client)
    resp = await client.post("/v1/wcs/notes", json=_note_payload(transcript["id"]))
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data", "meta"}
    assert body["meta"]["count"] == 1


async def test_create_note_output_shape(client) -> None:
    transcript = await _create_transcript(client)
    note = await _create_note(client, transcript["id"])
    assert "id" in note
    assert "transcript_id" in note
    assert "created_at" in note
    assert note["session_type"] == "private_lesson"
    assert note["instructors"] == ["Kaiano"]
    assert note["students"] == ["Sarah"]
    assert note["organization"] == ""
    assert note["visibility"] == "private"
    assert note["model"] == "claude-sonnet-4-6"
    assert note["provider"] == "anthropic"
    assert note["is_default_visible"] is False
    assert isinstance(note["notes_json"], dict)


async def test_create_note_invalid_transcript_id(client) -> None:
    resp = await client.post(
        "/v1/wcs/notes",
        json=_note_payload(str(uuid.uuid4())),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "transcript_not_found"


async def test_create_note_invalid_session_type(client) -> None:
    """class_attended is no longer a valid session type."""
    transcript = await _create_transcript(client)
    resp = await client.post(
        "/v1/wcs/notes",
        json=_note_payload(transcript["id"], session_type="class_attended"),
    )
    assert resp.status_code == 422


async def test_create_note_group_class_payload(client) -> None:
    """Group class notes have organization instead of students."""
    transcript = await _create_transcript(client)
    note = await _create_note(
        client,
        transcript["id"],
        session_type="group_class",
        instructors=["Kaiano"],
        students=[],
        organization="Swingesota Westie Academy",
    )
    assert note["session_type"] == "group_class"
    assert note["organization"] == "Swingesota Westie Academy"
    assert note["students"] == []


async def test_create_note_multiple_instructors(client) -> None:
    """Multiple instructors are stored and returned correctly."""
    transcript = await _create_transcript(client)
    note = await _create_note(
        client,
        transcript["id"],
        instructors=["Margie", "Kaiano"],
        students=["Sarah"],
    )
    assert note["instructors"] == ["Margie", "Kaiano"]
    assert note["students"] == ["Sarah"]


async def test_create_note_null_session_date(client) -> None:
    """session_date is optional — None is valid."""
    transcript = await _create_transcript(client)
    note = await _create_note(client, transcript["id"], session_date=None)
    assert note["session_date"] is None


async def test_create_note_malformed_session_date_is_tolerated(client) -> None:
    """Unparseable session_date is stored as null rather than erroring."""
    transcript = await _create_transcript(client)
    note = await _create_note(
        client, transcript["id"], session_date="sometime last winter"
    )
    assert note["session_date"] is None


# ── GET /v1/wcs/notes ─────────────────────────────────────────────────────────


async def test_list_notes_empty(client) -> None:
    resp = await client.get("/v1/wcs/notes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["meta"]["count"] == 0
    assert body["meta"]["total"] == 0


async def test_list_all_notes_returns_created_notes_for_admin(client) -> None:
    transcript = await _create_transcript(client)
    await _create_note(client, transcript["id"])
    await _create_note(
        client,
        transcript["id"],
        session_type="group_class",
        students=[],
        organization="Swingesota",
    )

    resp = await client.get("/v1/wcs/notes/all")
    assert resp.status_code == 200
    j = resp.json()
    assert j["meta"]["count"] == 2
    assert j["meta"]["total"] == 2


async def test_list_all_notes_filter_by_session_type(client) -> None:
    transcript = await _create_transcript(client)
    await _create_note(client, transcript["id"], session_type="private_lesson")
    await _create_note(
        client,
        transcript["id"],
        session_type="group_class",
        students=[],
        organization="Swingesota",
    )
    await _create_note(
        client,
        transcript["id"],
        session_type="group_class",
        students=[],
        organization="Freedom Swing",
    )

    resp = await client.get("/v1/wcs/notes/all", params={"session_type": "group_class"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 2
    data = body["data"]
    assert len(data) == 2
    assert all(n["session_type"] == "group_class" for n in data)


async def test_list_all_notes_filter_by_visibility(client) -> None:
    transcript = await _create_transcript(client)
    await _create_note(client, transcript["id"], visibility="private")
    await _create_note(client, transcript["id"], visibility="public")

    resp = await client.get("/v1/wcs/notes/all", params={"visibility": "public"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 1
    data = body["data"]
    assert len(data) == 1
    assert data[0]["visibility"] == "public"


async def test_list_all_notes_pagination(client) -> None:
    transcript = await _create_transcript(client)
    for _ in range(5):
        await _create_note(client, transcript["id"])

    resp = await client.get("/v1/wcs/notes/all", params={"limit": 3, "offset": 0})
    rj = resp.json()
    assert rj["meta"]["count"] == 3
    assert rj["meta"]["total"] == 5

    resp2 = await client.get("/v1/wcs/notes/all", params={"limit": 3, "offset": 3})
    r2 = resp2.json()
    assert r2["meta"]["count"] == 2
    assert r2["meta"]["total"] == 5


# ── GET /v1/wcs/notes/{id} ────────────────────────────────────────────────────


async def test_get_note_happy_path(client) -> None:
    transcript = await _create_transcript(client)
    note = await _create_note(client, transcript["id"])

    resp = await client.get(f"/v1/wcs/notes/{note['id']}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == note["id"]


async def test_get_note_not_found(client) -> None:
    resp = await client.get(f"/v1/wcs/notes/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "note_not_found"


# ── PATCH /v1/wcs/notes/{id} ─────────────────────────────────────────────────


async def test_patch_note_visibility(client) -> None:
    transcript = await _create_transcript(client)
    note = await _create_note(client, transcript["id"], visibility="private")
    assert note["visibility"] == "private"

    resp = await client.patch(
        f"/v1/wcs/notes/{note['id']}",
        json={"visibility": "public"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["visibility"] == "public"


async def test_patch_note_visibility_toggle_private_public_and_back(client) -> None:
    transcript = await _create_transcript(client)
    note = await _create_note(client, transcript["id"], visibility="private")

    pub = await client.patch(
        f"/v1/wcs/notes/{note['id']}",
        json={"visibility": "public"},
    )
    assert pub.status_code == 200
    assert pub.json()["data"]["visibility"] == "public"

    priv = await client.patch(
        f"/v1/wcs/notes/{note['id']}",
        json={"visibility": "private"},
    )
    assert priv.status_code == 200
    assert priv.json()["data"]["visibility"] == "private"


async def test_patch_note_not_found(client) -> None:
    resp = await client.patch(
        f"/v1/wcs/notes/{uuid.uuid4()}",
        json={"visibility": "public"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "note_not_found"


async def test_patch_note_invalid_visibility(client) -> None:
    transcript = await _create_transcript(client)
    note = await _create_note(client, transcript["id"])

    resp = await client.patch(
        f"/v1/wcs/notes/{note['id']}",
        json={"visibility": "friends_only"},
    )
    assert resp.status_code == 422
