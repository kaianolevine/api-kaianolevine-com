from __future__ import annotations

from sqlalchemy import text


async def test_evaluations_endpoints(client) -> None:
    list_resp = await client.get("/v1/evaluations", params={"limit": 50, "offset": 0})
    assert list_resp.status_code == 200
    list_json = list_resp.json()
    assert list_json["data"] == []
    assert list_json["meta"]["count"] == 0

    summary_resp = await client.get("/v1/evaluations/summary")
    assert summary_resp.status_code == 200
    summary_json = summary_resp.json()
    assert summary_json["data"] == []
    assert summary_json["meta"]["count"] == 0

    post_resp = await client.post(
        "/v1/evaluations",
        json={
            "repo": "api-kaianolevine-com",
            "dimension": "pipeline_consistency",
            "severity": "ERROR",
            "run_id": "run-123",
            "finding": "Pipeline did not complete ingestion as expected.",
            "suggestion": (
                "Ensure the ingest step is called and fails fast on unrecoverable errors."
            ),
            "standards_version": "6.0",
            "source": "flow_inline",
            "flow_name": "update-dj-set-collection",
        },
    )
    assert post_resp.status_code == 200
    created = post_resp.json()["data"]
    assert created["repo"] == "api-kaianolevine-com"
    assert created["dimension"] == "pipeline_consistency"
    assert created["severity"] == "ERROR"
    assert created["run_id"] == "run-123"
    assert created["finding"]
    assert created["suggestion"]
    assert created["standards_version"] == "6.0"
    assert created["source"] == "flow_inline"
    assert created["flow_name"] == "update-dj-set-collection"
    assert created["evaluated_at"]

    list_resp2 = await client.get(
        "/v1/evaluations",
        params={
            "repo": "api-kaianolevine-com",
            "dimension": "pipeline_consistency",
            "severity": "ERROR",
            "limit": 10,
            "offset": 0,
        },
    )
    assert list_resp2.status_code == 200
    j2 = list_resp2.json()
    assert j2["meta"]["count"] == 1
    assert j2["data"][0]["id"] == created["id"]

    summary_resp2 = await client.get("/v1/evaluations/summary")
    s2 = summary_resp2.json()
    assert s2["meta"]["count"] == 1
    assert s2["data"][0]["dimension"] == "pipeline_consistency"
    assert s2["data"][0]["error_count"] == 1
    assert s2["data"][0]["warn_count"] == 0
    assert s2["data"][0]["info_count"] == 0
    assert s2["data"][0]["most_recent"]

    # Validation error envelope
    bad = await client.post(
        "/v1/evaluations",
        json={
            "repo": "api-kaianolevine-com",
            "dimension": "pipeline_consistency",
            "severity": "ERROR",
        },
    )
    assert bad.status_code == 422
    bad_json = bad.json()
    assert bad_json["error"]["code"] == "validation_error"
    assert isinstance(bad_json["error"].get("details"), list)
    assert len(bad_json["error"]["details"]) >= 1


async def test_evaluation_source_is_none_when_omitted(client) -> None:
    resp = await client.post(
        "/v1/evaluations",
        json={
            "repo": "api-kaianolevine-com",
            "dimension": "pipeline_consistency",
            "severity": "INFO",
            "finding": "Pipeline completed normally.",
        },
    )
    assert resp.status_code == 200
    created = resp.json()["data"]
    assert created["source"] is None


async def test_evaluation_flow_name_is_none_when_omitted(client) -> None:
    resp = await client.post(
        "/v1/evaluations",
        json={
            "repo": "api-kaianolevine-com",
            "dimension": "pipeline_consistency",
            "severity": "INFO",
            "finding": "Pipeline completed normally.",
            "source": "flow_inline",
        },
    )
    assert resp.status_code == 200
    created = resp.json()["data"]
    assert created["flow_name"] is None


async def test_list_evaluations_only_returns_latest_run_per_repo_source(
    client, async_engine
) -> None:
    older = await client.post(
        "/v1/evaluations",
        json={
            "repo": "api-kaianolevine-com",
            "dimension": "pipeline_consistency",
            "severity": "WARN",
            "run_id": "run-older",
            "finding": "This finding belongs to an older run.",
            "source": "flow_inline",
        },
    )
    assert older.status_code == 200

    newer = await client.post(
        "/v1/evaluations",
        json={
            "repo": "api-kaianolevine-com",
            "dimension": "pipeline_consistency",
            "severity": "ERROR",
            "run_id": "run-newer",
            "finding": "This finding belongs to the latest run.",
            "source": "flow_inline",
        },
    )
    assert newer.status_code == 200

    # Force deterministic ordering for SQLite tests where inserts can share a timestamp.
    async with async_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE pipeline_evaluations SET evaluated_at = :older_at WHERE run_id = :older_run_id"
            ),
            {"older_at": "2024-01-01 00:00:00", "older_run_id": "run-older"},
        )
        await conn.execute(
            text(
                "UPDATE pipeline_evaluations SET evaluated_at = :newer_at WHERE run_id = :newer_run_id"
            ),
            {"newer_at": "2024-01-02 00:00:00", "newer_run_id": "run-newer"},
        )

    list_resp = await client.get(
        "/v1/evaluations",
        params={
            "repo": "api-kaianolevine-com",
            "limit": 50,
            "offset": 0,
        },
    )
    assert list_resp.status_code == 200
    body = list_resp.json()

    returned_run_ids = [row["run_id"] for row in body["data"]]
    assert "run-newer" in returned_run_ids
    assert "run-older" not in returned_run_ids


async def test_list_evaluations_returns_all_findings_same_run_id_even_if_timestamps_differ(
    client, async_engine
) -> None:
    """All rows sharing the latest run_id for a repo+source are returned."""
    first = await client.post(
        "/v1/evaluations",
        json={
            "repo": "mono-repo",
            "dimension": "structural_conformance",
            "severity": "ERROR",
            "run_id": "run-same-1",
            "finding": "Finding A",
            "source": "ci",
        },
    )
    assert first.status_code == 200
    id_a = first.json()["data"]["id"]

    second = await client.post(
        "/v1/evaluations",
        json={
            "repo": "mono-repo",
            "dimension": "pipeline_consistency",
            "severity": "WARN",
            "run_id": "run-same-1",
            "finding": "Finding B",
            "source": "ci",
        },
    )
    assert second.status_code == 200
    id_b = second.json()["data"]["id"]

    async with async_engine.begin() as conn:
        await conn.execute(
            text("UPDATE pipeline_evaluations SET evaluated_at = :t1 WHERE id = :id_a"),
            {
                "t1": "2024-06-01 10:00:00",
                "id_a": id_a,
            },
        )
        await conn.execute(
            text("UPDATE pipeline_evaluations SET evaluated_at = :t2 WHERE id = :id_b"),
            {
                "t2": "2024-06-01 10:00:01",
                "id_b": id_b,
            },
        )

    list_resp = await client.get(
        "/v1/evaluations",
        params={"repo": "mono-repo", "limit": 50, "offset": 0},
    )
    assert list_resp.status_code == 200
    body = list_resp.json()
    returned_ids = {row["id"] for row in body["data"]}
    assert id_a in returned_ids
    assert id_b in returned_ids
    assert body["meta"]["count"] == 2


async def test_evaluations_summary_uses_latest_run_id_not_partial_timestamp_rows(
    client, async_engine
) -> None:
    """Summary counts only include findings from the latest run per repo+source."""
    await client.post(
        "/v1/evaluations",
        json={
            "repo": "summ-repo",
            "dimension": "cd_readiness",
            "severity": "INFO",
            "run_id": "run-old-s",
            "finding": "Old",
            "source": "flow",
        },
    )
    await client.post(
        "/v1/evaluations",
        json={
            "repo": "summ-repo",
            "dimension": "cd_readiness",
            "severity": "ERROR",
            "run_id": "run-new-s",
            "finding": "New only",
            "source": "flow",
        },
    )

    async with async_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE pipeline_evaluations SET evaluated_at = :older "
                "WHERE run_id = :rid"
            ),
            {"older": "2023-01-01 00:00:00", "rid": "run-old-s"},
        )
        await conn.execute(
            text(
                "UPDATE pipeline_evaluations SET evaluated_at = :newer "
                "WHERE run_id = :rid"
            ),
            {"newer": "2023-06-01 00:00:00", "rid": "run-new-s"},
        )

    summary_resp = await client.get("/v1/evaluations/summary")
    assert summary_resp.status_code == 200
    s = summary_resp.json()
    assert s["meta"]["count"] == 1
    row = s["data"][0]
    assert row["dimension"] == "cd_readiness"
    assert row["error_count"] == 1
    assert row["warn_count"] == 0
    assert row["info_count"] == 0
