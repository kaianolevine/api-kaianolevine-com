from __future__ import annotations

import uuid


async def test_sets_endpoints_contract(client) -> None:
    payload = {
        "set_date": "2026-03-08",
        "venue": "MADjam",
        "source_file": "2026-03-08 MADjam.csv",
        "tracks": [
            {
                "play_order": 2,
                "play_time": "13:02:00",
                "title": "Song B",
                "artist": "Artist B",
                "genre": "House",
                "bpm": 124.0,
                "release_year": 2020,
                "length_secs": 200,
            },
            {
                "play_order": 1,
                "play_time": "13:01:00",
                "title": "Song A",
                "artist": "Artist A",
                "genre": "House",
                "bpm": 120.0,
                "release_year": 2019,
                "length_secs": 180,
            },
        ],
    }

    ingest = await client.post("/v1/ingest", json=payload)
    assert ingest.status_code == 200
    set_id = ingest.json()["data"]["set_id"]

    # List sets with year + venue partial
    list_resp = await client.get(
        "/v1/sets",
        params={"year": 2026, "venue": "mad", "limit": 50, "offset": 0},
    )
    assert list_resp.status_code == 200
    list_json = list_resp.json()
    assert "data" in list_json and "meta" in list_json
    assert list_json["meta"]["version"] == "1.0"
    assert list_json["meta"]["count"] == len(list_json["data"])
    assert any(item["id"] == set_id for item in list_json["data"])

    # Set detail includes ordered track list.
    detail_resp = await client.get(f"/v1/sets/{set_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["venue"] == "MADjam"
    assert len(detail["tracks"]) == 2
    assert detail["tracks"][0]["play_order"] == 1
    assert detail["tracks"][1]["play_order"] == 2

    tracks_resp = await client.get(f"/v1/sets/{set_id}/tracks")
    assert tracks_resp.status_code == 200
    tracks = tracks_resp.json()["data"]
    assert [t["title"] for t in tracks] == ["Song A", "Song B"]

    missing = await client.get(f"/v1/sets/{uuid.uuid4()}")
    assert missing.status_code == 404
    err = missing.json()
    assert "error" in err and "code" in err["error"] and "message" in err["error"]
