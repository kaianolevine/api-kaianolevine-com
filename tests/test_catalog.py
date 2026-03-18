from __future__ import annotations

import uuid


async def test_catalog_endpoints_and_patch(client) -> None:
    payload = {
        "set_date": "2026-03-08",
        "venue": "MADjam",
        "source_file": "2026-03-08 MADjam.csv",
        "tracks": [
            {
                "play_order": 1,
                "play_time": "13:01:00",
                "title": "Sundays",
                "artist": "Emotional Oranges",
                "genre": "R&B",
                "bpm": 98.0,
                "release_year": 2019,
                "length_secs": 189,
            }
        ],
    }
    ingest = await client.post("/v1/ingest", json=payload)
    assert ingest.status_code == 200

    list_resp = await client.get("/v1/catalog", params={"limit": 10, "offset": 0})
    assert list_resp.status_code == 200
    list_json = list_resp.json()
    assert list_json["meta"]["count"] == 1
    catalog_id = list_json["data"][0]["id"]

    detail_resp = await client.get(f"/v1/catalog/{catalog_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["id"] == catalog_id
    assert detail["play_count"] == 1
    assert len(detail["play_history"]) == 1
    assert detail["play_history"][0]["set_date"] == "2026-03-08"

    # Protected: PATCH sets source to manual.
    patch_resp = await client.patch(
        f"/v1/catalog/{catalog_id}",
        json={"genre": "Soul", "bpm": 99.0, "release_year": 2020},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()["data"]
    assert patched["source"] == "manual"
    assert patched["genre"] == "Soul"
    assert patched["bpm"] == 99.0
    assert patched["release_year"] == 2020

    missing = await client.patch(
        f"/v1/catalog/{uuid.uuid4()}",
        json={"genre": "Soul"},
    )
    assert missing.status_code == 404
    err = missing.json()
    assert err["error"]["code"] == "not_found"
