from __future__ import annotations

import hashlib
import hmac
import json

import pytest
import respx
from httpx import AsyncClient, Response

SECRET = "test-github-secret"
DISCORD_URL = "https://discord.test/api/webhooks/1/token"
DISCORD_GITHUB_URL = f"{DISCORD_URL}/github"


def _signed(payload: dict, event: str) -> tuple[bytes, dict[str, str]]:
    """Serialize once and sign exactly those bytes, as GitHub does."""
    body = json.dumps(payload).encode("utf-8")
    digest = hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return body, {
        "Content-Type": "application/json",
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": "delivery-1",
        "X-Hub-Signature-256": f"sha256={digest}",
    }


def _workflow_run(conclusion: str | None, *, action: str = "completed") -> dict:
    return {
        "action": action,
        "repository": {"full_name": "kaianolevine/example"},
        "workflow_run": {
            "name": "CI",
            "status": "completed" if action == "completed" else "in_progress",
            "conclusion": conclusion,
        },
    }


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_github_webhook_rejects_missing_signature(client: AsyncClient) -> None:
    """No signature is not a trusted caller, whatever the body says."""
    resp = await client.post(
        "/v1/webhooks/github",
        content=json.dumps(_workflow_run("failure")).encode(),
        headers={"Content-Type": "application/json", "X-GitHub-Event": "workflow_run"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_github_webhook_rejects_wrong_signature(client: AsyncClient) -> None:
    """A signature computed with the wrong secret is rejected."""
    body, headers = _signed(_workflow_run("failure"), "workflow_run")
    headers["X-Hub-Signature-256"] = "sha256=" + "0" * 64
    resp = await client.post("/v1/webhooks/github", content=body, headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_github_webhook_rejects_tampered_body(client: AsyncClient) -> None:
    """A body edited after signing no longer matches its digest."""
    body, headers = _signed(_workflow_run("failure"), "workflow_run")
    resp = await client.post(
        "/v1/webhooks/github",
        content=body.replace(b"failure", b"success"),
        headers=headers,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Ping
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_github_webhook_ping_is_acknowledged(client: AsyncClient) -> None:
    """The creation ping answers 200 and reaches Discord not at all."""
    route = respx.post(DISCORD_GITHUB_URL).mock(return_value=Response(204))
    body, headers = _signed({"zen": "Design for failure."}, "ping")

    resp = await client.post("/v1/webhooks/github", content=body, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["data"] == {
        "forwarded": False,
        "event": "ping",
        "outcome": None,
        "reason": "ping",
    }
    assert not route.called


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_github_webhook_forwards_failure(client: AsyncClient) -> None:
    """A failed run reaches Discord as the exact bytes GitHub signed."""
    route = respx.post(DISCORD_GITHUB_URL).mock(return_value=Response(204))
    body, headers = _signed(_workflow_run("failure"), "workflow_run")

    resp = await client.post("/v1/webhooks/github", content=body, headers=headers)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["forwarded"] is True
    assert data["outcome"] == "failure"
    assert route.called
    sent = route.calls.last.request
    assert sent.content == body
    assert sent.headers["X-GitHub-Event"] == "workflow_run"


@pytest.mark.parametrize("conclusion", ["timed_out", "cancelled"])
@respx.mock
@pytest.mark.asyncio
async def test_github_webhook_forwards_timeout_and_cancel(
    client: AsyncClient, conclusion: str
) -> None:
    """Timed-out and cancelled runs are failures for notification purposes."""
    route = respx.post(DISCORD_GITHUB_URL).mock(return_value=Response(204))
    body, headers = _signed(_workflow_run(conclusion), "workflow_run")

    resp = await client.post("/v1/webhooks/github", content=body, headers=headers)

    assert resp.json()["data"]["forwarded"] is True
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_github_webhook_drops_success(client: AsyncClient) -> None:
    """A passing run answers 200 and posts nothing. This is the whole point."""
    route = respx.post(DISCORD_GITHUB_URL).mock(return_value=Response(204))
    body, headers = _signed(_workflow_run("success"), "workflow_run")

    resp = await client.post("/v1/webhooks/github", content=body, headers=headers)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["forwarded"] is False
    assert data["reason"] == "not_a_failure"
    assert not route.called


@respx.mock
@pytest.mark.asyncio
async def test_github_webhook_drops_in_progress(client: AsyncClient) -> None:
    """A null conclusion mid-run means 'not yet', not 'fine'."""
    route = respx.post(DISCORD_GITHUB_URL).mock(return_value=Response(204))
    body, headers = _signed(_workflow_run(None, action="requested"), "workflow_run")

    resp = await client.post("/v1/webhooks/github", content=body, headers=headers)

    assert resp.json()["data"]["reason"] == "not_completed"
    assert not route.called


@respx.mock
@pytest.mark.asyncio
async def test_github_webhook_drops_duplicate_check_run(client: AsyncClient) -> None:
    """check_run repeats what workflow_run already said, so it is not forwarded."""
    route = respx.post(DISCORD_GITHUB_URL).mock(return_value=Response(204))
    payload = {
        "action": "completed",
        "repository": {"full_name": "kaianolevine/example"},
        "check_run": {"status": "completed", "conclusion": "failure"},
    }
    body, headers = _signed(payload, "check_run")

    resp = await client.post("/v1/webhooks/github", content=body, headers=headers)

    assert resp.json()["data"]["reason"] == "event_not_forwarded"
    assert not route.called


@respx.mock
@pytest.mark.asyncio
async def test_github_webhook_forwards_failing_status_event(
    client: AsyncClient,
) -> None:
    """The legacy status event carries its outcome flat, under a different name."""
    route = respx.post(DISCORD_GITHUB_URL).mock(return_value=Response(204))
    payload = {
        "state": "failure",
        "context": "ci/external",
        "repository": {"full_name": "kaianolevine/example"},
    }
    body, headers = _signed(payload, "status")

    resp = await client.post("/v1/webhooks/github", content=body, headers=headers)

    assert resp.json()["data"]["forwarded"] is True
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_github_webhook_drops_pending_status_event(client: AsyncClient) -> None:
    """A pending commit status is noise by the same rule."""
    route = respx.post(DISCORD_GITHUB_URL).mock(return_value=Response(204))
    body, headers = _signed({"state": "pending"}, "status")

    resp = await client.post("/v1/webhooks/github", content=body, headers=headers)

    assert resp.json()["data"]["reason"] == "not_a_failure"
    assert not route.called


@respx.mock
@pytest.mark.asyncio
async def test_github_webhook_answers_200_when_discord_is_down(
    client: AsyncClient,
) -> None:
    """A Discord outage must not become a 5xx GitHub disables the webhook over."""
    respx.post(DISCORD_GITHUB_URL).mock(return_value=Response(500, text="nope"))
    body, headers = _signed(_workflow_run("failure"), "workflow_run")

    resp = await client.post("/v1/webhooks/github", content=body, headers=headers)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["forwarded"] is False
    assert data["reason"] == "delivery_failed"


# ---------------------------------------------------------------------------
# POST /v1/notify
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_notify_posts_to_bare_webhook_url(client: AsyncClient) -> None:
    """Ad-hoc messages go to the plain URL — /github is for GitHub's shape only."""
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))

    resp = await client.post("/v1/notify", json={"content": "deploy finished"})

    assert resp.status_code == 200
    assert resp.json()["data"]["forwarded"] is True
    assert json.loads(route.calls.last.request.content) == {
        "content": "deploy finished"
    }


@respx.mock
@pytest.mark.asyncio
async def test_notify_passes_embeds_through(client: AsyncClient) -> None:
    """Embeds reach Discord unmodified."""
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))
    embed = {"title": "Nightly", "description": "3 sets ingested", "color": 5763719}

    resp = await client.post(
        "/v1/notify", json={"embeds": [embed], "username": "deejay-cog"}
    )

    assert resp.status_code == 200
    body = json.loads(route.calls.last.request.content)
    assert body["embeds"] == [embed]
    assert body["username"] == "deejay-cog"


@pytest.mark.asyncio
async def test_notify_rejects_empty_message(client: AsyncClient) -> None:
    """A message with neither content nor embeds is a validation error here."""
    resp = await client.post("/v1/notify", json={})
    assert resp.status_code == 422


@respx.mock
@pytest.mark.asyncio
async def test_notify_reports_delivery_failure(client: AsyncClient) -> None:
    """First-party callers get the truth: a rejected send is a 502, not a 200."""
    respx.post(DISCORD_URL).mock(return_value=Response(400, text="bad embed"))

    resp = await client.post("/v1/notify", json={"content": "x"})

    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "notify_failed"
