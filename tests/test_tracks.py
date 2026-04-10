from __future__ import annotations

import uuid


def _full_track(
    play_order: int,
    title: str,
    artist: str,
    *,
    genre: str = "House",
    bpm: float = 120.0,
) -> dict:
    return {
        "play_order": play_order,
        "play_time": "13:01:00",
        "title": title,
        "artist": artist,
        "genre": genre,
        "bpm": bpm,
        "release_year": 2019,
        "length_secs": 180,
    }


async def _ingest(
    client, source_file: str, tracks: list[dict], set_date: str = "2026-03-08"
) -> None:
    r = await client.post(
        "/v1/ingest",
        json={
            "set_date": set_date,
            "venue": "MADjam",
            "source_file": source_file,
            "tracks": tracks,
        },
    )
    assert r.status_code == 200
    assert r.json()["meta"]["total"] == 1


async def test_tracks_get_list_genre_filter(client) -> None:
    await _ingest(
        client,
        "t-genre-a.csv",
        [_full_track(1, "A", "A1", genre="House")],
    )
    await _ingest(
        client,
        "t-genre-b.csv",
        [_full_track(1, "B", "B1", genre="Techno")],
    )

    resp = await client.get("/v1/tracks", params={"genre": "House"})
    assert resp.status_code == 200
    j = resp.json()
    assert j["meta"]["total"] == 1
    assert j["meta"]["count"] == 1
    assert j["data"][0]["genre"] == "House"


async def test_tracks_get_list_bpm_min_bpm_max_filters(client) -> None:
    await _ingest(
        client,
        "t-bpm-low.csv",
        [_full_track(1, "Low", "A", bpm=100.0)],
    )
    await _ingest(
        client,
        "t-bpm-mid.csv",
        [_full_track(1, "Mid", "B", bpm=122.0)],
    )
    await _ingest(
        client,
        "t-bpm-high.csv",
        [_full_track(1, "High", "C", bpm=135.0)],
    )

    resp = await client.get("/v1/tracks", params={"bpm_min": 120.0, "bpm_max": 125.0})
    assert resp.status_code == 200
    j = resp.json()
    assert j["meta"]["total"] == 1
    assert j["data"][0]["title"] == "Mid"


async def test_tracks_get_list_year_filter(client) -> None:
    await _ingest(
        client,
        "t-y1.csv",
        [_full_track(1, "Y1", "A")],
        set_date="2025-07-01",
    )
    await _ingest(
        client,
        "t-y2.csv",
        [_full_track(1, "Y2", "B")],
        set_date="2026-01-01",
    )

    resp = await client.get("/v1/tracks", params={"year": 2026})
    assert resp.status_code == 200
    j = resp.json()
    assert j["meta"]["total"] == 1
    assert j["data"][0]["title"] == "Y2"


async def test_tracks_get_list_data_quality_filter(client) -> None:
    await _ingest(
        client,
        "t-min.csv",
        [
            {
                "play_order": 1,
                "play_time": None,
                "title": "Min",
                "artist": "A",
            }
        ],
    )
    await _ingest(
        client,
        "t-complete.csv",
        [_full_track(1, "Full", "B")],
    )

    resp = await client.get("/v1/tracks", params={"data_quality": "complete"})
    assert resp.status_code == 200
    j = resp.json()
    assert j["meta"]["total"] == 1
    assert j["data"][0]["data_quality"] == "complete"


async def test_tracks_get_list_artist_filter_and_meta_total(client) -> None:
    await _ingest(
        client,
        "t-art.csv",
        [_full_track(1, "Song A", "Artist A")],
    )

    list_resp = await client.get(
        "/v1/tracks",
        params={"artist": "Artist", "limit": 50, "offset": 0},
    )
    assert list_resp.status_code == 200
    j = list_resp.json()
    assert j["meta"]["total"] == 1
    assert j["meta"]["count"] == 1
    track_id = j["data"][0]["id"]
    assert j["data"][0]["title"] == "Song A"
    assert j["data"][0]["catalog_id"] is not None

    detail_resp = await client.get(f"/v1/tracks/{track_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["id"] == track_id
    assert detail["set_date"] == "2026-03-08"


async def test_tracks_get_id_unknown_uuid_returns_404(client) -> None:
    missing = await client.get(f"/v1/tracks/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
