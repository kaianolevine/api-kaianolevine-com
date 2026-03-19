from __future__ import annotations


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
            "repo": "deejay-sets-api",
            "dimension": "pipeline_consistency",
            "severity": "ERROR",
            "run_id": "run-123",
            "finding": "Pipeline did not complete ingestion as expected.",
            "suggestion": (
                "Ensure the ingest step is called and fails fast on unrecoverable errors."
            ),
            "standards_version": "6.0",
        },
    )
    assert post_resp.status_code == 200
    created = post_resp.json()["data"]
    assert created["repo"] == "deejay-sets-api"
    assert created["dimension"] == "pipeline_consistency"
    assert created["severity"] == "ERROR"
    assert created["run_id"] == "run-123"
    assert created["finding"]
    assert created["suggestion"]
    assert created["standards_version"] == "6.0"
    assert created["evaluated_at"]

    list_resp2 = await client.get(
        "/v1/evaluations",
        params={
            "repo": "deejay-sets-api",
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
        json={"repo": "deejay-sets-api", "dimension": "pipeline_consistency", "severity": "ERROR"},
    )
    assert bad.status_code == 422
    bad_json = bad.json()
    assert bad_json["error"]["code"] == "validation_error"
