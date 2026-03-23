from __future__ import annotations


async def test_prefect_webhook_crashed(client) -> None:
    resp = await client.post(
        "/v1/prefect-webhook",
        json={
            "flow_run_id": "run-1",
            "flow_name": "DJ Import",
            "state_name": "Crashed",
            "state_type": "CRASHED",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["severity"] == "ERROR"
    assert "Crashed" in data["finding"]


async def test_prefect_webhook_failed(client) -> None:
    resp = await client.post(
        "/v1/prefect-webhook",
        json={
            "flow_run_id": "run-2",
            "flow_name": "DJ Import",
            "state_name": "Failed",
            "state_type": "FAILED",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["severity"] == "WARN"


async def test_prefect_webhook_completed(client) -> None:
    resp = await client.post(
        "/v1/prefect-webhook",
        json={
            "flow_run_id": "run-3",
            "flow_name": "DJ Import",
            "state_name": "Completed",
            "state_type": "COMPLETED",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["severity"] == "INFO"


async def test_prefect_webhook_unknown_payload(client) -> None:
    resp = await client.post(
        "/v1/prefect-webhook",
        json={
            "flow_run_id": "run-4",
            "flow_name": "DJ Import",
            "state_name": "Completed",
            "state_type": "COMPLETED",
            "unexpected_field": "kept",
        },
    )
    assert resp.status_code == 200


async def test_prefect_webhook_missing_fields(client) -> None:
    resp = await client.post("/v1/prefect-webhook", json={})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "unknown" in data["finding"]

