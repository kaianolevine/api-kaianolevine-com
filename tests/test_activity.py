"""The running list: what it tallies, what it suppresses, what it reports.

The wiring tests at the bottom are the point. A tally is collected inside
SQLAlchemy's greenlet and read back in the middleware, two context copies
away from where it was opened; a unit test of ``Recorder`` proves the
arithmetic and nothing at all about whether that path holds.
"""

from __future__ import annotations

import asyncio

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import async_sessionmaker

from kaianolevine_api.config import get_settings
from kaianolevine_api.models import FeatureFlag as DbFeatureFlag
from kaianolevine_api.services import activity

DISCORD_URL = "https://discord.test/api/webhooks/1/token"


async def _drain() -> None:
    """Let the fire-and-forget deliveries land before asserting on them."""
    for _ in range(3):
        if not activity._in_flight:
            break
        await asyncio.gather(*list(activity._in_flight), return_exceptions=True)
    await asyncio.sleep(0)


# ── Tally arithmetic ────────────────────────────────────────────────────


def test_summary_renders_marks_per_table():
    rec = activity.Recorder()
    rec.record("tracks", activity.CREATED)
    rec.record("tracks", activity.CREATED)
    rec.record("tracks", activity.UPDATED)
    rec.record("sets", activity.DELETED)
    rec.promote()

    assert rec.summary(set()) == "`sets` -1\n`tracks` +2 ~1"


def test_uncommitted_work_is_not_reported():
    rec = activity.Recorder()
    rec.record("tracks", activity.CREATED)
    assert rec.summary(set()) == ""


def test_rollback_discards_flushed_work():
    rec = activity.Recorder()
    rec.record("tracks", activity.CREATED)
    rec.discard()
    rec.promote()
    assert rec.summary(set()) == ""


def test_suppressed_table_alone_produces_no_message():
    rec = activity.Recorder()
    rec.record("identity_audit_events", activity.CREATED)
    rec.promote()
    assert rec.summary({"identity_audit_events"}) == ""


def test_bulk_statements_are_counted_as_statements():
    rec = activity.Recorder()
    rec.record("wcs_source_extractions", activity.BULK)
    rec.promote()
    assert rec.summary(set()) == "`wcs_source_extractions` *1"
    assert rec.has_bulk() is True


# ── Fault policy ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "kind", "expected"),
    [
        (500, None, True),
        (502, "human", True),
        (403, "human", False),
        (404, "human", False),
        (422, "human", False),
        (403, "machine", True),
        (422, "machine", True),
        (200, "machine", False),
        (201, "human", False),
    ],
)
def test_fault_policy(status, kind, expected):
    assert activity.is_notifiable_fault(status, kind, get_settings()) is expected


def test_faults_can_be_turned_off(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "NOTIFY_FAULTS", False)
    assert activity.is_notifiable_fault(500, "machine", settings) is False


def test_excluded_paths_cover_children():
    settings = get_settings()
    assert activity._excluded("/health", settings) is True
    assert activity._excluded("/v1/webhooks/github", settings) is True
    assert activity._excluded("/v1/flags", settings) is False


# ── Wiring ──────────────────────────────────────────────────────────────


@respx.mock
async def test_committed_change_reaches_discord(client, async_engine):
    """A real route, a real commit, one message — and the audit row silent."""
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))

    # Seeded outside the request, so this write is not part of the tally.
    sessionmaker = async_sessionmaker(
        async_engine, expire_on_commit=False, autoflush=False
    )
    async with sessionmaker() as session:
        session.add(
            DbFeatureFlag(
                owner_id="dev-owner",
                name="flags.deejay_api.ingest_enabled",
                enabled=True,
                description="Enable ingest endpoint",
            )
        )
        await session.commit()

    resp = await client.patch(
        "/v1/flags/flags.deejay_api.ingest_enabled", json={"enabled": False}
    )
    assert resp.status_code == 200
    await _drain()

    bodies = [call.request.content.decode() for call in route.calls]
    assert bodies, "the committed change should have produced a Discord message"
    assert any("feature_flags" in body for body in bodies)
    # The audit row is written on every authorized request. If it reaches the
    # channel, the feed is an access log wearing a different hat.
    assert not any("identity_audit_events" in body for body in bodies)


@respx.mock
async def test_read_only_request_says_nothing(client):
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))
    resp = await client.get("/v1/flags")
    assert resp.status_code == 200
    await _drain()
    assert route.call_count == 0


@respx.mock
async def test_denied_human_is_not_reported(client):
    """A guard doing its job is not news, whatever the status code."""
    route = respx.post(DISCORD_URL).mock(return_value=Response(204))
    resp = await client.patch("/v1/flags/flags.does.not.exist", json={"enabled": True})
    assert resp.status_code in (403, 404)
    await _drain()
    assert route.call_count == 0


@respx.mock
async def test_unhandled_exception_is_reported_and_re_raised():
    """The middleware sees the raise, not the 500 the outer handler renders."""
    from fastapi import FastAPI

    route = respx.post(DISCORD_URL).mock(return_value=Response(204))

    app = FastAPI()
    app.middleware("http")(activity.activity_middleware)

    @app.get("/boom")
    async def boom() -> dict:
        raise RuntimeError("the thing broke")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        resp = await c.get("/boom")
    await _drain()

    assert resp.status_code == 500
    assert route.call_count == 1
    body = route.calls[0].request.content.decode()
    assert "RuntimeError" in body
    assert "the thing broke" in body
