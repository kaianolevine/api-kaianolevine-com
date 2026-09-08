"""Discord notification routes — one for GitHub, one for the fleet.

Two callers, two admission rules, one destination.

``POST /v1/webhooks/github`` is GitHub's ci-status org webhook. It is public
in the sense that no bearer token reaches it, and gated instead by the
signature GitHub computes over the raw body with a shared secret — the only
credential GitHub can present. It exists to make the channel quiet: GitHub
posts every check result, and this route forwards only the ones that failed.

``POST /v1/notify`` is the fleet's own path for ad-hoc messages, and takes the
ordinary machine credential every other first-party route takes
(``notify.messages.send``). Nothing about it is GitHub-shaped.

Both return promptly and neither retries. GitHub disables a webhook that keeps
receiving 5xx, so a Discord outage must not become one; see
``services.discord`` for where delivery failures go instead.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from identity.types import Principal
from mini_app_polis.logger import (
    LOG_FAILURE,
    LOG_START,
    LOG_WARNING,
    get_logger,
    with_log_prefix,
)

from ..auth import require_scope
from ..config import Settings, get_settings
from ..schemas import (
    Envelope,
    NotificationResult,
    NotifyRequest,
    api_error,
    success_envelope,
)
from ..services import discord

router = APIRouter()
logger = get_logger()

#: ``conclusion`` values that mean a human should hear about it now. GitHub
#: also emits ``neutral``, ``skipped``, ``stale`` and ``action_required``;
#: none of those is a build that broke, and ``action_required`` in particular
#: fires on every first-time-contributor approval prompt. Add one here if it
#: turns out to matter — this frozenset is the whole policy.
FAILING_CONCLUSIONS = frozenset({"failure", "timed_out", "cancelled"})

#: ``state`` values on the legacy ``status`` event, which has no ``conclusion``.
FAILING_STATES = frozenset({"failure", "error"})

#: Where the outcome lives in each payload shape this route understands.
_CONCLUSION_KEYS = ("workflow_run", "check_run", "check_suite")


def verify_github_signature(
    *, secret: str, raw_body: bytes, signature: str | None
) -> bool:
    """Whether ``signature`` is GitHub's HMAC-SHA256 over exactly these bytes.

    The comparison is constant-time, and the digest is taken over the raw body
    rather than a re-serialization of it: JSON round-tripping changes
    whitespace and key order, and either one turns a valid signature into an
    invalid one.
    """
    if not signature:
        return False
    expected = (
        "sha256="
        + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature)


def extract_outcome(event: str, payload: dict[str, Any]) -> tuple[str | None, bool]:
    """Return ``(outcome, completed)`` for whichever payload shape arrived.

    ``completed`` is false while a run is still queued or in progress, where
    ``conclusion`` is null and means "not yet" rather than "fine". Treating
    those two the same is the bug this returns two values to avoid.
    """
    if event == "status":
        # The legacy commit-status event carries its outcome flat and has no
        # lifecycle action: a status is only ever reported once it is known.
        state = payload.get("state")
        return (str(state) if state else None), True

    for key in _CONCLUSION_KEYS:
        if key in event or key in payload:
            body = payload.get(key)
            if not isinstance(body, dict):
                continue
            conclusion = body.get("conclusion")
            completed = (
                payload.get("action") == "completed"
                or body.get("status") == "completed"
            )
            return (str(conclusion) if conclusion else None), completed

    return None, False


def is_failure(event: str, outcome: str | None) -> bool:
    """Whether this outcome is one worth interrupting someone for."""
    if outcome is None:
        return False
    normalized = outcome.lower()
    if event == "status":
        return normalized in FAILING_STATES
    return normalized in FAILING_CONCLUSIONS


@router.post(
    "/webhooks/github",
    response_model=Envelope[NotificationResult],
    summary="GitHub CI webhook → Discord (failures only)",
    description=(
        "Receives the org-level ci-status webhook, verifies GitHub's "
        "X-Hub-Signature-256 over the raw body, and forwards only failing "
        "runs to Discord. Intentionally unauthenticated in the bearer-token "
        "sense: the shared-secret signature is the credential, because it is "
        "the only one GitHub can present."
    ),
    include_in_schema=False,
)
async def github_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Envelope[NotificationResult]:
    """Forward failing GitHub check results to Discord and drop the rest.

    Everything that is not a failure still answers 200. A drop is a decision
    this route made, not an error GitHub should retry, and the delivery log in
    GitHub's UI reads far better when the only red entries are real ones.
    """
    raw_body = await request.body()
    event = request.headers.get("X-GitHub-Event", "")
    delivery = request.headers.get("X-GitHub-Delivery")

    secret = (settings.GITHUB_WEBHOOK_SECRET or "").strip()
    if not secret:
        # Fail closed and loudly. Accepting unsigned payloads because the
        # secret is missing would turn a configuration gap into an open relay
        # into the notification channel.
        logger.error(
            with_log_prefix(
                LOG_FAILURE,
                "GITHUB_WEBHOOK_SECRET is unset; rejecting github webhook "
                f"event={event} delivery={delivery}",
            )
        )
        raise api_error(500, "config_error", "GitHub webhook secret is not configured")

    if not verify_github_signature(
        secret=secret,
        raw_body=raw_body,
        signature=request.headers.get("X-Hub-Signature-256"),
    ):
        logger.warning(
            with_log_prefix(
                LOG_WARNING,
                f"github webhook signature rejected event={event} delivery={delivery}",
            )
        )
        raise api_error(401, "unauthorized", "Invalid webhook signature")

    if event == "ping":
        # Sent once when the webhook is created. Answering 200 is what turns
        # the delivery green in GitHub's UI; forwarding it would put a
        # meaningless embed in the channel on every settings change.
        logger.info(with_log_prefix(LOG_START, "github webhook ping acknowledged"))
        return _result(settings, event="ping", outcome=None, reason="ping")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise api_error(400, "parse_error", "Body is not valid JSON") from None
    if not isinstance(payload, dict):
        raise api_error(400, "parse_error", "Body is not a JSON object")

    if event not in settings.GITHUB_NOTIFY_EVENTS:
        # A single failing Actions run emits check_run (per job), check_suite
        # and workflow_run for the same failure. Forwarding all of them posts
        # the same news three times, so which shapes count is configuration
        # rather than a code change.
        return _result(
            settings, event=event, outcome=None, reason="event_not_forwarded"
        )

    outcome, completed = extract_outcome(event, payload)

    if not completed:
        return _result(settings, event=event, outcome=outcome, reason="not_completed")

    if not is_failure(event, outcome):
        return _result(settings, event=event, outcome=outcome, reason="not_a_failure")

    repo = (payload.get("repository") or {}).get("full_name", "unknown")
    logger.info(
        with_log_prefix(
            LOG_START,
            f"forwarding github failure repo={repo} event={event} "
            f"outcome={outcome} delivery={delivery}",
        )
    )

    forwarded = await discord.forward_github_event(
        settings=settings,
        raw_body=raw_body,
        event=event,
        delivery=delivery,
    )
    return _result(
        settings,
        event=event,
        outcome=outcome,
        reason="forwarded" if forwarded else "delivery_failed",
        forwarded=forwarded,
    )


@router.post(
    "/notify",
    response_model=Envelope[NotificationResult],
    summary="Send an ad-hoc Discord notification",
    description=(
        "First-party notification path for cogs and scripts. Takes a Discord "
        "message body (content and/or embeds) and posts it to the "
        "notification channel. Requires notify.messages.send."
    ),
)
async def notify(
    payload: NotifyRequest = Body(..., embed=False),
    principal: Principal = Depends(require_scope("notify.messages.send")),
    settings: Settings = Depends(get_settings),
) -> Envelope[NotificationResult]:
    """Post one message to the notification channel on the caller's behalf.

    A rejected delivery answers 502 rather than a cheerful 200: the caller is
    first-party and can decide for itself whether a missed notification is
    worth failing over. Callers for which it is not should ignore the status
    rather than have this route lie about what happened.
    """
    logger.info(
        with_log_prefix(
            LOG_START,
            f"notify requested principal={principal.display_name or principal.subject}",
        )
    )

    sent = await discord.send_message(settings=settings, payload=payload.to_discord())
    if not sent:
        raise api_error(502, "notify_failed", "Discord rejected the notification")

    return _result(
        settings, event="notify", outcome=None, reason="forwarded", forwarded=True
    )


def _result(
    settings: Settings,
    *,
    event: str,
    outcome: str | None,
    reason: str,
    forwarded: bool = False,
) -> Envelope[NotificationResult]:
    """Build the standard envelope around one notification decision."""
    return success_envelope(
        NotificationResult(
            forwarded=forwarded, event=event, outcome=outcome, reason=reason
        ),
        count=1,
        total=1,
        version=settings.API_VERSION,
    )
