"""Prefect flow-state webhook — notification, not a finding.

Three properties, in the order they matter:

1. **It writes no rows.** A crashed flow is run status; the evaluations
   table holds graded findings only.
2. **It notifies failing states and drops the rest**, answering 200
   either way so Prefect does not retry a decision.
3. **It is open by default, and honours a secret when one is set.** The
   route is the crash backstop, so a credential that could quietly turn
   it off costs more than the noise it prevents — but the check exists
   for the day that trade changes.
"""

from __future__ import annotations

import json

import pytest
import respx
from httpx import AsyncClient, Response

from kaianolevine_api.config import get_settings

TOKEN = "test-prefect-token"
DISCORD_URL = "https://discord.test/api/webhooks/1/token"

CRASHED = {
    "flow_run_id": "run-1",
    "flow_name": "process-new-csv-files",
    "state_name": "Crashed",
    "state_type": "CRASHED",
}


async def _post(client: AsyncClient, payload: dict, *, token: str | None = TOKEN):
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["X-Prefect-Token"] = token
    return await client.post("/v1/prefect-webhook", json=payload, headers=headers)


# ---------------------------------------------------------------------------
# Optional secret
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_no_secret_configured_accepts_the_callback(
    client: AsyncClient, monkeypatch
) -> None:
    """The default. Prefect posts flow states; nothing gates that."""
    monkeypatch.setenv("PREFECT_WEBHOOK_SECRET", "")
    get_settings.cache_clear()
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))

    resp = await _post(client, CRASHED, token=None)

    assert resp.status_code == 200
    assert route.called


@pytest.mark.asyncio
async def test_wrong_token_is_rejected_when_a_secret_is_set(
    client: AsyncClient,
) -> None:
    """Configured means enforced — the check is real when it is on."""
    resp = await _post(client, CRASHED, token="not-the-token")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@respx.mock
@pytest.mark.asyncio
async def test_rejected_callback_never_reaches_discord(client: AsyncClient) -> None:
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))
    await _post(client, CRASHED, token="wrong")
    assert not route.called


@respx.mock
@pytest.mark.asyncio
async def test_payload_text_cannot_mention_anyone(client: AsyncClient) -> None:
    """Caller-supplied text lands in an embed, and embeds do not mention.

    The display name is looked up from the flow map rather than taken
    from the payload, so neither half of the message is caller-chosen in
    a way that can reach past the channel.
    """
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))

    await _post(client, {**CRASHED, "flow_name": "@everyone deploy now"})

    body = json.loads(route.calls.last.request.content)
    assert "content" not in body
    assert body["username"] == "unknown"
    assert "@everyone" in body["embeds"][0]["title"]


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_crashed_flow_notifies(client: AsyncClient) -> None:
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))

    resp = await _post(client, CRASHED)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["forwarded"] is True
    assert data["outcome"] == "CRASHED"
    body = json.loads(route.calls.last.request.content)
    embed = body["embeds"][0]
    assert embed["title"] == "deejay-cog · process-new-csv-files"
    assert "Crashed" in embed["description"]
    assert "run-1" in embed["description"]
    assert "prefect_webhook" in embed["footer"]["text"]


@pytest.mark.parametrize("state", ["FAILED", "CANCELLED", "TIMEDOUT"])
@respx.mock
@pytest.mark.asyncio
async def test_other_failing_states_notify(client: AsyncClient, state: str) -> None:
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))
    resp = await _post(client, {**CRASHED, "state_type": state, "state_name": state})
    assert resp.json()["data"]["forwarded"] is True
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_completed_state_is_dropped(client: AsyncClient) -> None:
    """A widened automation must not turn every green run into a message."""
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))

    resp = await _post(
        client, {**CRASHED, "state_type": "COMPLETED", "state_name": "Completed"}
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["reason"] == "state_not_notified"
    assert not route.called


@respx.mock
@pytest.mark.asyncio
async def test_unmapped_flow_still_notifies(client: AsyncClient) -> None:
    """An unknown flow crashing is not a reason to stay quiet."""
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))

    resp = await _post(client, {**CRASHED, "flow_name": "brand-new-flow"})

    assert resp.json()["data"]["forwarded"] is True
    embed = json.loads(route.calls.last.request.content)["embeds"][0]
    assert embed["title"] == "unknown · brand-new-flow"


@respx.mock
@pytest.mark.asyncio
async def test_missing_fields_do_not_crash_the_route(client: AsyncClient) -> None:
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))
    resp = await _post(client, {"state_type": "CRASHED"})
    assert resp.status_code == 200
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_delivery_failure_answers_200(client: AsyncClient) -> None:
    """Prefect should not retry a Discord outage."""
    respx.post(DISCORD_URL).mock(return_value=Response(500, text="nope"))
    resp = await _post(client, CRASHED)
    assert resp.status_code == 200
    assert resp.json()["data"]["reason"] == "delivery_failed"


# ---------------------------------------------------------------------------
# No rows
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_writes_no_evaluation_rows(client: AsyncClient, db_session) -> None:
    """Regression: run status stopped being a finding.

    If this route starts writing again, the evaluations table quietly
    refills with rows nothing graded — the conflation the split exists
    to end.
    """
    from sqlalchemy import select

    from kaianolevine_api.models import PipelineEvaluation

    respx.post(DISCORD_URL).mock(return_value=Response(204))
    await _post(client, CRASHED)

    rows = (await db_session.execute(select(PipelineEvaluation))).scalars().all()
    assert rows == []
