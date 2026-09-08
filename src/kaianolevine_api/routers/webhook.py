"""Prefect flow-state webhook — the backstop crash report.

Prefect Cloud calls this when a flow run enters a failing state. It used
to write a row to ``pipeline_evaluations``; it does not any more. A flow
that crashed was never graded against a revision of the standards
catalog, which is why those rows had to carry a null
``standards_version`` to stop Pipeline Health claiming they had been.
Run status is a notification. The evaluations table holds what the
evaluator produced and nothing else.

**Why this exists at all, given cogs report their own failures.**
``mini_app_polis.pipeline_status.make_failure_hook`` runs *inside the
cog process*. When that process is healthy enough to run its own hooks,
it reports first and better — it knows what the flow was doing. When it
is not — OOM-killed, SIGKILL'd mid-run, the container replaced under it
— the hook never fires and the only witness left is Prefect Cloud. This
route is that witness.

The overlap is deliberate. An ordinary ``Failed`` run may well produce
two messages, one from the cog and one from here. That is the cheaper
error: a crash nobody hears about is worse than a crash mentioned
twice, and the two are distinguishable by their ``source``. Narrow
``PREFECT_NOTIFY_STATES`` to ``["CRASHED"]`` if the duplicates get
tiring — the states that reach Discord are configuration, not code.

**Auth is optional, and off unless configured.** The caller is Prefect
Cloud posting flow states, and what a stranger could do with the URL is
bounded: the message is embeds-only, so nothing in it can mention anyone
(Discord does not fire mentions from embed content), the display name
comes from the flow map rather than the payload, and there is no write
and no read behind it. The worst case is noise in a channel.

Against that, a required header is a new way for *this* route to fail
silently — and it is the backstop, the thing that reports when a cog was
too dead to report itself. One Prefect automation missed when adding the
header and its callbacks 401 into the void, precisely when they matter.
A credential that can quietly disable the last witness costs more than
the nuisance it prevents.

So ``PREFECT_WEBHOOK_SECRET`` is honoured when set and skipped when not.
Setting it is a decision available later without a code change; leaving
it unset is the default and is not an oversight.
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from mini_app_polis import logger as logger_mod
from mini_app_polis.logger import LOG_START, LOG_WARNING, with_log_prefix

from ..config import Settings, get_settings
from ..schemas import (
    Envelope,
    NotificationResult,
    PrefectWebhookPayload,
    api_error,
    success_envelope,
)
from ..services import discord

router = APIRouter()
log = logger_mod.get_logger()

#: Header Prefect Cloud is configured to send. Not a signature: Prefect
#: automations post a templated body and cannot compute an HMAC over it,
#: so a shared secret in a header is the strongest credential available
#: on this path. It is compared in constant time all the same.
SECRET_HEADER = "X-Prefect-Token"

#: Flow names to the repo that owns them, so a message names the cog
#: rather than only the flow.
_FLOW_REPO_MAP: dict[str, str] = {
    "conformance-check": "evaluator-cog",
    "pipeline-eval": "evaluator-cog",
    "process-transcript": "transcription-cog",
    "voicenotes-ingest": "transcription-cog",
    "update-dj-set-collection": "deejay-cog",
    "generate-summaries": "deejay-cog",
    "process-set": "deejay-cog",
    "process-new-csv-files": "deejay-cog",
    "ingest-live-history": "deejay-cog",
    "wiki-curator-cog": "wiki-curator-cog",
}

_STATE_COLORS: dict[str, int] = {
    "CRASHED": 0xDA3633,
    "FAILED": 0xD29922,
    "CANCELLED": 0x6E7681,
    "TIMEDOUT": 0xD29922,
}
_DEFAULT_COLOR = 0x58A6FF


def verify_secret(*, expected: str, provided: str | None) -> bool:
    """Constant-time comparison of the shared secret."""
    if not provided:
        return False
    return hmac.compare_digest(expected, provided)


def build_message(payload: PrefectWebhookPayload, repo: str) -> dict[str, Any]:
    """Render one Prefect flow-state event as a Discord message."""
    state_name = payload.state_name or "unknown"
    state_type = (payload.state_type or "").upper()
    flow_name = payload.flow_name or "unknown"

    description_parts = [f"Flow entered **{state_name}**"]
    if payload.flow_run_id:
        description_parts.append(f"run `{payload.flow_run_id}`")

    embed: dict[str, Any] = {
        "title": f"{repo} · {flow_name}",
        "description": " · ".join(description_parts),
        "color": _STATE_COLORS.get(state_type, _DEFAULT_COLOR),
        "footer": {"text": f"{state_type or 'UNKNOWN'} · prefect_webhook"},
    }
    if payload.end_time:
        embed["footer"]["text"] += f" · ended {payload.end_time}"

    return {"embeds": [embed], "username": repo}


@router.post(
    "/prefect-webhook",
    response_model=Envelope[NotificationResult],
    summary="Prefect flow-state webhook → Discord",
    description=(
        "Receives Prefect Cloud flow-state callbacks and notifies Discord "
        "for failing states. Authenticated by a shared secret in the "
        "X-Prefect-Token header. Writes no rows: a crashed flow is run "
        "status, not a graded finding."
    ),
    include_in_schema=False,
)
async def prefect_webhook(
    request: Request,
    payload: PrefectWebhookPayload = Body(..., embed=False),
    settings: Settings = Depends(get_settings),
) -> Envelope[NotificationResult]:
    """Notify Discord when Prefect reports a flow run in a failing state."""
    # Enforced only when a secret is configured. Unset is the default and
    # means "no token expected" rather than "reject everything" — see the
    # module docstring for why fail-open is the right way round here.
    secret = (settings.PREFECT_WEBHOOK_SECRET or "").strip()
    if secret and not verify_secret(
        expected=secret, provided=request.headers.get(SECRET_HEADER)
    ):
        log.warning(with_log_prefix(LOG_WARNING, "prefect webhook token rejected"))
        raise api_error(401, "unauthorized", "Invalid webhook token")

    state_type = (payload.state_type or "").upper()
    flow_name = payload.flow_name or "unknown"
    repo = _FLOW_REPO_MAP.get(flow_name, "unknown")

    if state_type not in settings.PREFECT_NOTIFY_STATES:
        # Prefect automations are normally scoped to failing states, so a
        # Completed callback arriving here means the automation was
        # widened. Drop it rather than announce every successful run.
        return _result(settings, state=state_type or None, reason="state_not_notified")

    if repo == "unknown":
        # Still forwarded — an unmapped flow crashing is not a reason to
        # stay quiet, and the message names the flow either way.
        log.warning(
            with_log_prefix(
                LOG_WARNING,
                f"prefect webhook: unmapped flow_name={flow_name}",
            )
        )

    log.info(
        with_log_prefix(
            LOG_START,
            f"prefect webhook repo={repo} flow={flow_name} state={state_type}",
        )
    )

    forwarded = await discord.send_message(
        settings=settings, payload=build_message(payload, repo)
    )
    return _result(
        settings,
        state=state_type,
        reason="forwarded" if forwarded else "delivery_failed",
        forwarded=forwarded,
    )


def _result(
    settings: Settings,
    *,
    state: str | None,
    reason: str,
    forwarded: bool = False,
) -> Envelope[NotificationResult]:
    """Build the standard envelope around one webhook decision."""
    return success_envelope(
        NotificationResult(
            forwarded=forwarded,
            event="prefect_webhook",
            outcome=state,
            reason=reason,
        ),
        count=1,
        total=1,
        version=settings.API_VERSION,
    )
