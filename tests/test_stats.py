from __future__ import annotations


async def test_stats_endpoints(client) -> None:
    # 2025 set (1 play)
    await client.post(
        "/v1/ingest",
        json={
            "set_date": "2025-05-01",
            "venue": "MADjam",
            "source_file": "2025-05-01 MADjam.csv",
            "tracks": [
                {
                    "play_order": 1,
                    "play_time": "13:01:00",
                    "title": "Song A",
                    "artist": "Artist X",
                    "genre": "House",
                    "bpm": 120.0,
                    "release_year": 2019,
                    "length_secs": 180,
                }
            ],
        },
    )

    # 2026 set (2 plays)
    await client.post(
        "/v1/ingest",
        json={
            "set_date": "2026-03-08",
            "venue": "MADjam",
            "source_file": "2026-03-08 MADjam.csv",
            "tracks": [
                {
                    "play_order": 1,
                    "play_time": "13:01:00",
                    "title": "Song A",
                    "artist": "Artist X",
                    "genre": "House",
                    "bpm": 121.0,
                    "release_year": 2019,
                    "length_secs": 180,
                },
                {
                    "play_order": 2,
                    "play_time": "13:02:00",
                    "title": "Song B",
                    "artist": "Artist Y",
                    "genre": "House",
                    "bpm": 124.0,
                    "release_year": 2020,
                    "length_secs": 200,
                },
            ],
        },
    )

    overview = await client.get("/v1/stats/overview")
    assert overview.status_code == 200
    o = overview.json()["data"]
    assert o["total_sets"] == 2
    assert o["total_plays"] == 3
    assert o["unique_tracks"] == 2
    assert o["years_active"] == 2
    assert o["most_played_artist"] == "Artist X"

    by_year = await client.get("/v1/stats/by-year")
    assert by_year.status_code == 200
    years = {item["year"]: item for item in by_year.json()["data"]}
    assert years[2025]["set_count"] == 1
    assert years[2025]["track_count"] == 1
    assert years[2026]["set_count"] == 1
    assert years[2026]["track_count"] == 2

    top_artists = await client.get("/v1/stats/top-artists")
    assert top_artists.status_code == 200
    ta = top_artists.json()["data"]
    assert ta[0]["artist"] == "Artist X"
    assert ta[0]["play_count"] == 2

    top_tracks = await client.get("/v1/stats/top-tracks")
    assert top_tracks.status_code == 200
    tt = top_tracks.json()["data"]
    assert tt[0]["play_count"] == 2

    method_not_allowed = await client.post("/v1/stats/overview", json={})
    assert method_not_allowed.status_code == 405
