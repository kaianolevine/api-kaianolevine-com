from __future__ import annotations

import uuid


def _track(
    *,
    play_order: int,
    title: str,
    artist: str,
    genre: str = "House",
    bpm: float = 120.0,
    release_year: int = 2019,
    length_secs: int = 180,
) -> dict:
    return {
        "play_order": play_order,
        "play_time": "13:01:00",
        "title": title,
        "artist": artist,
        "genre": genre,
        "bpm": bpm,
        "release_year": release_year,
        "length_secs": length_secs,
    }


async def _ingest_set(
    client,
    *,
    set_date: str,
    venue: str,
    source_file: str,
    tracks: list[dict],
) -> str:
    ingest = await client.post(
        "/v1/ingest",
        json={
            "set_date": set_date,
            "venue": venue,
            "source_file": source_file,
            "tracks": tracks,
        },
    )
    assert ingest.status_code == 200
    body = ingest.json()
    assert body["meta"]["total"] == 1
    return body["data"]["set_id"]


async def test_sets_get_list_venue_partial_match_case_insensitive(client) -> None:
    await _ingest_set(
        client,
        set_date="2026-03-08",
        venue="The BLUE Club",
        source_file="2026-03-08 blue.csv",
        tracks=[_track(play_order=1, title="A", artist="B")],
    )

    resp = await client.get("/v1/sets", params={"venue": "blue", "limit": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 1
    assert body["meta"]["count"] == 1
    assert body["data"][0]["venue"] == "The BLUE Club"


async def test_sets_get_list_date_from_date_to_filters(client) -> None:
    await _ingest_set(
        client,
        set_date="2026-06-15",
        venue="Venue A",
        source_file="2026-06-15 a.csv",
        tracks=[_track(play_order=1, title="A", artist="B")],
    )

    inside = await client.get(
        "/v1/sets",
        params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
    )
    assert inside.status_code == 200
    j = inside.json()
    assert j["meta"]["total"] == 1
    assert j["meta"]["count"] == 1

    outside = await client.get(
        "/v1/sets",
        params={"date_from": "2025-01-01", "date_to": "2026-05-01"},
    )
    assert outside.status_code == 200
    o = outside.json()
    assert o["meta"]["total"] == 0
    assert o["data"] == []


async def test_sets_get_list_limit_offset_meta_total_exceeds_page_count(client) -> None:
    for i in range(3):
        await _ingest_set(
            client,
            set_date=f"2026-04-{i + 1:02d}",
            venue="Paginate Venue",
            source_file=f"2026-04-pag-{i}.csv",
            tracks=[_track(play_order=1, title=f"T{i}", artist="A")],
        )

    page = await client.get("/v1/sets", params={"limit": 1, "offset": 0})
    assert page.status_code == 200
    p = page.json()
    assert p["meta"]["count"] == 1
    assert p["meta"]["total"] == 3


async def test_sets_get_set_id_tracks_ordered_by_play_order(client) -> None:
    set_id = await _ingest_set(
        client,
        set_date="2026-03-08",
        venue="MADjam",
        source_file="2026-03-08 order.csv",
        tracks=[
            _track(play_order=2, title="Song B", artist="B"),
            _track(play_order=1, title="Song A", artist="A"),
        ],
    )

    tracks_resp = await client.get(f"/v1/sets/{set_id}/tracks")
    assert tracks_resp.status_code == 200
    tj = tracks_resp.json()
    assert tj["meta"]["total"] == 2
    assert [x["play_order"] for x in tj["data"]] == [1, 2]
    assert [x["title"] for x in tj["data"]] == ["Song A", "Song B"]


async def test_sets_get_set_id_unknown_uuid_returns_404_not_found(client) -> None:
    missing = await client.get(f"/v1/sets/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


async def test_sets_get_list_year_and_meta_total(client) -> None:
    """Smoke: year filter + list envelope includes total."""
    set_id = await _ingest_set(
        client,
        set_date="2026-03-08",
        venue="MADjam",
        source_file="2026-03-08 smoke.csv",
        tracks=[
            _track(play_order=2, title="Song B", artist="Artist B"),
            _track(play_order=1, title="Song A", artist="Artist A"),
        ],
    )

    list_resp = await client.get(
        "/v1/sets",
        params={"year": 2026, "venue": "mad", "limit": 50, "offset": 0},
    )
    assert list_resp.status_code == 200
    list_json = list_resp.json()
    assert list_json["meta"]["total"] >= 1
    assert list_json["meta"]["count"] == len(list_json["data"])
    matching = next(item for item in list_json["data"] if item["id"] == set_id)
    assert matching["track_count"] == 2

    detail_resp = await client.get(f"/v1/sets/{set_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["tracks"][0]["play_order"] == 1
    assert detail["tracks"][1]["play_order"] == 2
