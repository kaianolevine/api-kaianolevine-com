"""Tests for WCS notes endpoints — contract, happy path, failure paths, output shape."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from kaianolevine_api.models import WcsSourceExtraction, WcsTranscript


@pytest.fixture(autouse=True)
async def seed_dev_owner_wcs_admin(reset_db, async_engine) -> None:
    """Seeds dev-owner as WCS admin so all note tests run as an authenticated admin."""
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
    assert resp.status_code == 201
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
    assert resp.status_code == 201
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


async def test_create_transcript_new_file_returns_201(client) -> None:
    response = await client.post(
        "/v1/wcs/transcripts",
        json={
            "raw_text": "Sample transcript text.",
            "source_type": "unknown",
            "source_filename": "2025-06-28 Test > File",
            "drive_file_id": "drive_id_test_new",
        },
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["drive_file_id"] == "drive_id_test_new"


async def test_create_transcript_reingestion_returns_200_and_updates_text(
    client, async_engine
) -> None:
    initial = await client.post(
        "/v1/wcs/transcripts",
        json={
            "raw_text": "Original text.",
            "source_type": "unknown",
            "source_filename": "2025-06-28 Test > File",
            "drive_file_id": "drive_id_test_reingest",
        },
    )
    assert initial.status_code == 201
    initial_id = initial.json()["data"]["id"]

    reingest = await client.post(
        "/v1/wcs/transcripts",
        json={
            "raw_text": "Updated text after re-extraction.",
            "source_type": "unknown",
            "source_filename": "2025-06-28 Test > File",
            "drive_file_id": "drive_id_test_reingest",
        },
    )
    assert reingest.status_code == 200
    assert reingest.json()["data"]["id"] == initial_id

    sm = async_sessionmaker(async_engine, expire_on_commit=False)
    async with sm() as session:
        stored = await session.get(WcsTranscript, uuid.UUID(initial_id))
        assert stored is not None
        assert stored.raw_text == "Updated text after re-extraction."


def _source_payload_for_demote_test(transcript_id: str) -> dict:
    return {
        "transcript_id": transcript_id,
        "session_date": "2025-06-28",
        "session_type": "workshop",
        "instructors_raw": ["TestInstructor"],
        "students_raw": ["TestStudent"],
        "organization": "",
        "extractor_version": "test-1",
        "extractor_model": "test-model",
        "extractor_provider": "test",
        "prompt_version": "test-1",
        "raw_output": {
            "entities": [],
            "entity_definitions": [],
            "entity_relations": [],
            "drill_purposes": [],
            "technique_requirements": [],
            "common_mistakes": [],
            "competition_notes": [],
            "references": [],
        },
    }


async def test_create_transcript_reingestion_demotes_active_extractions(
    client, async_engine
) -> None:
    transcript_resp = await client.post(
        "/v1/wcs/transcripts",
        json={
            "raw_text": "Text v1.",
            "source_type": "unknown",
            "source_filename": "2025-06-28 Demote Test",
            "drive_file_id": "drive_id_test_demote",
        },
    )
    assert transcript_resp.status_code == 201
    transcript_id = transcript_resp.json()["data"]["id"]

    source_resp = await client.post(
        "/v1/wcs/sources",
        json=_source_payload_for_demote_test(transcript_id),
    )
    assert source_resp.status_code == 200
    source_id = uuid.UUID(source_resp.json()["data"]["id"])

    reingest_resp = await client.post(
        "/v1/wcs/transcripts",
        json={
            "raw_text": "Text v2.",
            "source_type": "unknown",
            "source_filename": "2025-06-28 Demote Test",
            "drive_file_id": "drive_id_test_demote",
        },
    )
    assert reingest_resp.status_code == 200

    sm = async_sessionmaker(async_engine, expire_on_commit=False)
    async with sm() as session:
        active = (
            (
                await session.execute(
                    select(WcsSourceExtraction).where(
                        WcsSourceExtraction.source_id == source_id,
                        WcsSourceExtraction.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert active == []


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


async def test_valid_session_date_still_parses(client) -> None:
    transcript = await _create_transcript(client)
    note = await _create_note(client, transcript["id"], session_date="2024-01-15")
    assert note["session_date"] == "2024-01-15"


@pytest.mark.parametrize(
    "bad_date", ["2026-09-09T14:00:00Z", "sometime last winter", "01/15/2024"]
)
async def test_invalid_session_date_is_rejected_not_dropped(client, bad_date) -> None:
    """A date the caller sent and the API cannot read is a request problem.

    It used to become NULL behind a 200, which sorted the note to the bottom
    of both listing queries and left it dateless in citations, while the cog
    saw nothing but successful writes.
    """
    transcript = await _create_transcript(client)
    resp = await client.post(
        "/v1/wcs/notes",
        json=_note_payload(transcript["id"], session_date=bad_date),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_session_date"


# ── GET /v1/wcs/notes ─────────────────────────────────────────────────────────


async def test_list_notes_empty(client) -> None:
    resp = await client.get("/v1/wcs/notes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["meta"]["count"] == 0
    assert body["meta"]["total"] == 0


async def test_list_all_notes_returns_created_notes(client) -> None:
    # NOTE: endpoint name predates the auth relaxation. /v1/wcs/notes/all
    # is currently authenticated-but-not-admin while service-account auth
    # is being designed; see TODO(service-auth) in routers/wcs_notes.py.

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
