from __future__ import annotations


def _payload(set_date: str, venue: str, source_file: str, tracks: list[dict]) -> dict:
    return {"set_date": set_date, "venue": venue, "source_file": source_file, "tracks": tracks}


async def test_ingest_reconciliation_confidence_escalation(client) -> None:
    # 1) Minimal first play => data_quality minimal; catalog new low.
    payload1 = _payload(
        "2026-03-08",
        "MADjam",
        "2026-03-08 MADjam.csv",
        [
            {
                "play_order": 1,
                "play_time": None,
                "title": "My Boo",
                "artist": "Artist feat. Someone",
                "genre": None,
                "bpm": None,
                "release_year": None,
                "length_secs": None,
            }
        ],
    )
    r1 = await client.post("/v1/ingest", json=payload1)
    assert r1.status_code == 200
    j1 = r1.json()
    assert set(j1.keys()) == {"data", "meta"}
    assert j1["meta"]["count"] == 1
    assert j1["meta"]["version"] == "1.0"
    assert j1["data"]["tracks_created"] == 1
    assert j1["data"]["catalog_new"] == 1
    assert j1["data"]["catalog_updated"] == 0
    assert j1["data"]["catalog_unchanged"] == 0
    set_id_1 = j1["data"]["set_id"]

    # 2) Add genre + bpm => catalog confidence low -> medium (play_count=2).
    payload2 = _payload(
        "2026-03-09",
        "MADjam",
        "2026-03-09 MADjam.csv",
        [
            {
                "play_order": 1,
                "play_time": None,
                "title": "My Boo (Radio Edit)",
                "artist": "Artist",
                "genre": "R&B",
                "bpm": 101.0,
                "release_year": None,
                "length_secs": None,
            }
        ],
    )
    r2 = await client.post("/v1/ingest", json=payload2)
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["data"]["catalog_new"] == 0
    assert j2["data"]["catalog_updated"] == 1
    assert j2["data"]["catalog_unchanged"] == 0

    # 3) Provide consistent bpm within +/-2 => medium -> high (play_count=3).
    payload3 = _payload(
        "2026-03-10",
        "MADjam",
        "2026-03-10 MADjam.csv",
        [
            {
                "play_order": 1,
                "play_time": "13:01:00",
                "title": "My Boo",
                "artist": "Artist",
                "genre": "R&B",
                "bpm": 102.0,
                "release_year": 2020,
                "length_secs": 189,
            }
        ],
    )
    r3 = await client.post("/v1/ingest", json=payload3)
    assert r3.status_code == 200
    j3 = r3.json()
    assert j3["data"]["catalog_new"] == 0
    assert j3["data"]["catalog_updated"] == 1
    assert j3["data"]["catalog_unchanged"] == 0

    # Verify catalog state via API.
    list_resp = await client.get("/v1/catalog", params={"limit": 10, "offset": 0})
    assert list_resp.status_code == 200
    list_json = list_resp.json()
    assert list_json["meta"]["count"] == 1
    catalog_id = list_json["data"][0]["id"]
    assert list_json["data"][0]["confidence"] == "high"
    assert list_json["data"][0]["play_count"] == 3

    detail_resp = await client.get(f"/v1/catalog/{catalog_id}")
    assert detail_resp.status_code == 200
    detail_json = detail_resp.json()
    assert detail_json["data"]["play_count"] == 3
    assert len(detail_json["data"]["play_history"]) == 3

    # Ensure set detail includes ordered tracks.
    set_detail = await client.get(f"/v1/sets/{set_id_1}")
    assert set_detail.status_code == 200
    detail = set_detail.json()["data"]
    assert len(detail["tracks"]) == 1

    # Validation error envelope
    bad = await client.post("/v1/ingest", json={"venue": "MADjam"})
    assert bad.status_code == 422
    bad_json = bad.json()
    assert bad_json["error"]["code"] == "validation_error"
