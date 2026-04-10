from __future__ import annotations

import uuid


def _track(**kwargs) -> dict:
    base = {
        "play_order": 1,
        "play_time": "13:01:00",
        "title": "Sundays",
        "artist": "Emotional Oranges",
        "genre": "R&B",
        "bpm": 98.0,
        "release_year": 2019,
        "length_secs": 189,
    }
    return {**base, **kwargs}


async def test_catalog_get_list_and_patch_source_manual(client) -> None:
    ingest = await client.post(
        "/v1/ingest",
        json={
            "set_date": "2026-03-08",
            "venue": "MADjam",
            "source_file": "2026-03-08 MADjam.csv",
            "tracks": [_track()],
        },
    )
    assert ingest.status_code == 200
    assert ingest.json()["meta"]["total"] == 1

    list_resp = await client.get("/v1/catalog", params={"limit": 10, "offset": 0})
    assert list_resp.status_code == 200
    list_json = list_resp.json()
    assert list_json["meta"]["total"] == 1
    assert list_json["meta"]["count"] == 1
    catalog_id = list_json["data"][0]["id"]
    assert list_json["data"][0]["confidence"] in ("low", "medium", "high")

    detail_resp = await client.get(f"/v1/catalog/{catalog_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["play_count"] == 1
    assert len(detail["play_history"]) == 1
    assert detail["play_history"][0]["set_date"] == "2026-03-08"

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
    assert missing.json()["error"]["code"] == "not_found"


async def test_catalog_get_list_confidence_filter(client) -> None:
    await client.post(
        "/v1/ingest",
        json={
            "set_date": "2026-01-01",
            "venue": "V1",
            "source_file": "cat-low.csv",
            "tracks": [
                {
                    "play_order": 1,
                    "title": "One",
                    "artist": "A",
                }
            ],
        },
    )
    r = await client.get("/v1/catalog", params={"confidence": "low"})
    assert r.status_code == 200
    j = r.json()
    assert j["meta"]["total"] == 1
    assert all(row["confidence"] == "low" for row in j["data"])


async def test_catalog_get_list_min_play_count_filter(client) -> None:
    await client.post(
        "/v1/ingest",
        json={
            "set_date": "2026-02-01",
            "venue": "V2",
            "source_file": "mpc-1.csv",
            "tracks": [_track(title="Repeat", artist="SameArtist")],
        },
    )
    await client.post(
        "/v1/ingest",
        json={
            "set_date": "2026-02-02",
            "venue": "V2",
            "source_file": "mpc-2.csv",
            "tracks": [_track(title="Repeat", artist="SameArtist")],
        },
    )

    r = await client.get("/v1/catalog", params={"min_play_count": 2})
    assert r.status_code == 200
    j = r.json()
    assert j["meta"]["total"] >= 1
    assert all(row["play_count"] >= 2 for row in j["data"])


async def test_catalog_get_list_artist_title_partial_filters(client) -> None:
    await client.post(
        "/v1/ingest",
        json={
            "set_date": "2026-03-01",
            "venue": "V3",
            "source_file": "ft-a.csv",
            "tracks": [
                _track(title="UniqueTitleX", artist="Alpha Singer"),
            ],
        },
    )

    by_artist = await client.get("/v1/catalog", params={"artist": "alpha"})
    assert by_artist.status_code == 200
    ja = by_artist.json()
    assert ja["meta"]["total"] == 1
    assert "Alpha" in ja["data"][0]["artist"]

    by_title = await client.get("/v1/catalog", params={"title": "uniquetitle"})
    assert by_title.status_code == 200
    jt = by_title.json()
    assert jt["meta"]["total"] == 1
    assert jt["data"][0]["title"] == "UniqueTitleX"


async def test_catalog_get_id_play_history_after_second_ingest(client) -> None:
    await client.post(
        "/v1/ingest",
        json={
            "set_date": "2026-04-01",
            "venue": "V4",
            "source_file": "hist-1.csv",
            "tracks": [_track(title="HistSong", artist="HistArt")],
        },
    )
    await client.post(
        "/v1/ingest",
        json={
            "set_date": "2026-04-02",
            "venue": "V4",
            "source_file": "hist-2.csv",
            "tracks": [_track(title="HistSong", artist="HistArt")],
        },
    )

    lst = await client.get("/v1/catalog", params={"title": "histsong"})
    cid = lst.json()["data"][0]["id"]

    detail = await client.get(f"/v1/catalog/{cid}")
    assert detail.status_code == 200
    d = detail.json()["data"]
    assert d["play_count"] == 2
    assert len(d["play_history"]) == 2


async def test_catalog_get_id_unknown_uuid_returns_404(client) -> None:
    r = await client.get(f"/v1/catalog/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
