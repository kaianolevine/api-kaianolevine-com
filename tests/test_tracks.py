from __future__ import annotations

import uuid


async def test_tracks_endpoints_contract(client) -> None:
    payload = {
        "set_date": "2026-03-08",
        "venue": "MADjam",
        "source_file": "2026-03-08 MADjam.csv",
        "tracks": [
            {
                "play_order": 1,
                "play_time": "13:01:00",
                "title": "Song A",
                "artist": "Artist A",
                "genre": "House",
                "bpm": 120.0,
                "release_year": 2019,
                "length_secs": 180,
            }
        ],
    }
    ingest = await client.post("/v1/ingest", json=payload)
    assert ingest.status_code == 200

    list_resp = await client.get(
        "/v1/tracks",
        params={"artist": "Artist", "limit": 50, "offset": 0},
    )
    assert list_resp.status_code == 200
    j = list_resp.json()
    assert j["meta"]["version"] == "1.0"
    assert len(j["data"]) == 1
    track_id = j["data"][0]["id"]
    assert j["data"][0]["title"] == "Song A"
    assert j["data"][0]["artist"] == "Artist A"
    assert j["data"][0]["data_quality"] == "complete"
    assert j["data"][0]["catalog_id"] is not None

    detail_resp = await client.get(f"/v1/tracks/{track_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["id"] == track_id
    assert detail["set_date"] == "2026-03-08"
    assert detail["venue"] == "MADjam"

    missing = await client.get(f"/v1/tracks/{uuid.uuid4()}")
    assert missing.status_code == 404
    err = missing.json()
    assert err["error"]["code"] == "not_found"
