"""Discord notification transport — the one place a Discord webhook is called.

Two shapes, one destination. GitHub's payloads go to the webhook's ``/github``
suffix, where Discord parses the event itself and renders the same embed it
would have rendered had GitHub posted to it directly. Everything else goes to
the bare webhook URL as an ordinary Discord message. The suffix is the whole
difference between the two and they are not interchangeable: a GitHub payload
posted to the bare URL is rejected, and a Discord message posted to ``/github``
is rejected the other way.

Delivery failures are logged and reported to Sentry, never raised. The caller
is either GitHub — which must not be handed a 5xx for a Discord outage, since
enough of those make GitHub disable the webhook — or one of the fleet's own
scripts, for which a dropped notification is not a failed job. Both want the
truth in Sentry and a 200 on the wire.
"""

from __future__ import annotations

from typing import Any

import httpx
import sentry_sdk
from mini_app_polis.logger import (
    LOG_FAILURE,
    LOG_SUCCESS,
    LOG_WARNING,
    get_logger,
    with_log_prefix,
)

from ..config import Settings

logger = get_logger()

#: Suffix Discord exposes for GitHub-shaped payloads.
GITHUB_SUFFIX = "/github"


def discord_base_url(settings: Settings) -> str | None:
    """The configured webhook URL with any ``/github`` suffix removed.

    Configuration holds one URL and this module decides which endpoint each
    payload shape needs, so a value pasted with the suffix already on it —
    the form GitHub's own docs hand you — still works for both routes.
    """
    raw = (settings.DISCORD_WEBHOOK_URL or "").strip().rstrip("/")
    if not raw:
        return None
    if raw.endswith(GITHUB_SUFFIX):
        raw = raw[: -len(GITHUB_SUFFIX)]
    return raw


async def _post(
    url: str,
    *,
    settings: Settings,
    content: bytes | None = None,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    context: str,
) -> bool:
    """POST to Discord, returning whether it accepted the message."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                content=content,
                json=json,
                headers=headers,
                timeout=settings.HTTP_CLIENT_TIMEOUT_SECS,
            )
    except httpx.HTTPError as exc:
        logger.error(
            with_log_prefix(LOG_FAILURE, f"discord post failed ({context}): {exc!r}")
        )
        sentry_sdk.capture_exception(exc)
        return False

    if resp.is_success:
        logger.info(
            with_log_prefix(
                LOG_SUCCESS, f"discord notified ({context}) status={resp.status_code}"
            )
        )
        return True

    # A non-2xx is Discord rejecting the message, not a transport fault: the
    # body says why and is worth having verbatim, since the usual causes are a
    # malformed embed or a revoked webhook.
    logger.error(
        with_log_prefix(
            LOG_FAILURE,
            f"discord rejected ({context}) status={resp.status_code} body={resp.text}",
        )
    )
    sentry_sdk.capture_message(
        f"Discord rejected notification ({context}): {resp.status_code}",
        level="error",
    )
    return False


async def forward_github_event(
    *,
    settings: Settings,
    raw_body: bytes,
    event: str,
    delivery: str | None = None,
) -> bool:
    """Forward GitHub's payload byte-for-byte to Discord's ``/github`` endpoint.

    The body is passed through unparsed. Discord renders the embed from the
    payload GitHub signed, so re-serializing it here would only introduce a
    version of the event that no longer matches the one whose signature was
    verified.
    """
    base = discord_base_url(settings)
    if base is None:
        logger.warning(
            with_log_prefix(
                LOG_WARNING,
                "DISCORD_WEBHOOK_URL is unset; dropping github event "
                f"event={event} delivery={delivery}",
            )
        )
        return False

    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": event,
    }
    if delivery:
        headers["X-GitHub-Delivery"] = delivery

    return await _post(
        f"{base}{GITHUB_SUFFIX}",
        settings=settings,
        content=raw_body,
        headers=headers,
        context=f"github/{event}",
    )


async def send_message(*, settings: Settings, payload: dict[str, Any]) -> bool:
    """Post an ordinary Discord message to the bare webhook URL."""
    base = discord_base_url(settings)
    if base is None:
        logger.warning(
            with_log_prefix(
                LOG_WARNING, "DISCORD_WEBHOOK_URL is unset; dropping notification"
            )
        )
        return False

    return await _post(base, settings=settings, json=payload, context="notify")
