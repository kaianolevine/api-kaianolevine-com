"""Discord notification routes — one for GitHub, one for the fleet.

Two callers, two admission rules, one destination.

``POST /v1/webhooks/github`` is the org-level webhook for both GitHub orgs. It
is public in the sense that no bearer token reaches it, and gated instead by
the signature GitHub computes over the raw body with a shared secret — the
only credential GitHub can present. It exists because GitHub's webhooks filter
by event type and nothing else: "pushes to main", "new pull requests" and
"releases, but not edits to old ones" are all decisions that can only be made
after the payload arrives, and this is where they are made.

``POST /v1/notify`` is the fleet's own path for ad-hoc messages, and takes the
ordinary machine credential every other first-party route takes
(``notify.messages.send``). Nothing about it is GitHub-shaped.

Two delivery shapes, because Discord's GitHub endpoint is not universal.
``push``, ``pull_request``, ``issues`` and ``release`` are rendered by Discord
itself, so those payloads are forwarded byte-for-byte to the webhook's
``/github`` suffix and Discord draws its own embed. ``workflow_run`` is not:
Discord accepts it, answers 204 and posts nothing. That silence is
indistinguishable from success at every layer above it, which is why the
workflow embed is built here and posted to the bare webhook URL as an ordinary
message instead.

Both routes return promptly and neither retries. GitHub disables a webhook that
keeps receiving 5xx, so a Discord outage must not become one; see
``services.discord`` for where delivery failures go instead.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
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


# ---------------------------------------------------------------------------
# Merge detection
# ---------------------------------------------------------------------------

#: GitHub's default subject for a merge commit made by the merge button.
_MERGE_COMMIT = re.compile(r"^Merge pull request #\d+ from ")

#: GitHub's default subject for a squash merge — the PR number in parentheses.
_SQUASH_COMMIT = re.compile(r"\(#\d+\)$")

# Rebase-and-merge is not detectable here. It replays the branch's original
# commits onto the default branch with their original subjects and no marker
# of the pull request they came from, so a rebase merge is announced twice:
# once as the pull request closing, once as a push. Recognising it would mean
# calling GitHub back to ask whether these shas belong to a merged PR, which
# puts a network round-trip and a token on the path of every push. Two
# messages on a rebase merge is the cheaper wrong answer.


# ---------------------------------------------------------------------------
# Workflow run presentation
# ---------------------------------------------------------------------------

#: Embed colours by conclusion. GitHub's own palette, so a red here is the red
#: on the run page rather than a second opinion about severity.
_CONCLUSION_COLORS: dict[str, int] = {
    "success": 0x2EA043,
    "failure": 0xDA3633,
    "timed_out": 0xD29922,
    "action_required": 0xD29922,
    "cancelled": 0x6E7681,
    "neutral": 0x6E7681,
    "skipped": 0x6E7681,
    "stale": 0x6E7681,
}
_DEFAULT_COLOR = 0x58A6FF


@dataclass(frozen=True)
class Decision:
    """What this route decided about one delivery, and how to act on it.

    ``message`` carries a Discord message body when the event has to be
    rendered here rather than by Discord. When it is None and ``forward`` is
    true, the original payload is passed through to Discord's ``/github``
    endpoint unchanged.
    """

    forward: bool
    reason: str
    outcome: str | None = None
    message: dict[str, Any] | None = None


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


def _subject(commit: dict[str, Any] | None) -> str:
    """First line of a commit message, which is all a notification needs."""
    message = str((commit or {}).get("message") or "")
    return message.splitlines()[0] if message else ""


def build_workflow_message(payload: dict[str, Any]) -> dict[str, Any]:
    """Render a completed workflow run as a Discord message.

    Built here rather than forwarded because Discord's GitHub endpoint ignores
    ``workflow_run`` entirely — it answers 204 and posts nothing, so a
    pass-through would look successful at every layer and appear nowhere.

    Everything in the embed is a link back to GitHub. The value of a build
    notification is getting to the log in one click, not reading a summary of
    what the log says.
    """
    run: dict[str, Any] = payload.get("workflow_run") or {}
    repo: dict[str, Any] = payload.get("repository") or {}

    conclusion = str(run.get("conclusion") or "unknown")
    repo_url = str(repo.get("html_url") or "")
    sha = str(run.get("head_sha") or "")

    description_parts: list[str] = []
    if sha and repo_url:
        subject = _subject(run.get("head_commit"))
        link = f"[`{sha[:7]}`]({repo_url}/commit/{sha})"
        description_parts.append(f"{link} {subject}".strip())
    elif sha:
        description_parts.append(f"`{sha[:7]}`")

    embed: dict[str, Any] = {
        "title": f"{run.get('name') or 'Workflow'} · {conclusion}",
        "color": _CONCLUSION_COLORS.get(conclusion, _DEFAULT_COLOR),
    }
    if run.get("html_url"):
        embed["url"] = run["html_url"]
    if description_parts:
        embed["description"] = "\n".join(description_parts)
    if repo.get("full_name"):
        author: dict[str, Any] = {"name": repo["full_name"]}
        if repo_url:
            author["url"] = repo_url
        embed["author"] = author

    footer_bits = [str(run.get("head_branch") or "")]
    if run.get("run_number"):
        footer_bits.append(f"run #{run['run_number']}")
    actor = (run.get("actor") or {}).get("login")
    if actor:
        footer_bits.append(str(actor))
    footer = " · ".join(bit for bit in footer_bits if bit)
    if footer:
        embed["footer"] = {"text": footer}

    if run.get("updated_at"):
        embed["timestamp"] = run["updated_at"]

    return {"embeds": [embed]}


# ---------------------------------------------------------------------------
# Per-event policy
#
# One function per event type, each answering the same question: does this
# particular delivery deserve a message? Kept apart rather than folded into one
# predicate because the reasons differ — a release is filtered by action, a
# push by branch, a workflow run by branch and lifecycle — and a single
# function that did all three would hide which rule dropped what.
# ---------------------------------------------------------------------------


def _decide_release(payload: dict[str, Any]) -> Decision:
    """Announce a release when it is published, and only then.

    The ``release`` event also fires for ``created``, ``edited``,
    ``prereleased``, ``released`` and ``deleted``. Fixing a typo in old release
    notes is not news, and ``created`` fires for drafts nobody can see yet.
    """
    action = str(payload.get("action") or "")
    if action != "published":
        return Decision(False, "action_not_published", outcome=action)
    tag = (payload.get("release") or {}).get("tag_name")
    return Decision(True, "forwarded", outcome=str(tag) if tag else action)


def _decide_push(payload: dict[str, Any], default_branch: str) -> Decision:
    """Announce direct pushes to the default branch, and nothing else.

    A merge is already announced by its pull request closing, so a push whose
    head commit looks like GitHub's own merge or squash commit is dropped
    rather than reported a second time. Branch deletions and tag pushes are
    not pushes to the default branch at all.
    """
    ref = str(payload.get("ref") or "")
    branch = ref.removeprefix("refs/heads/")
    if branch == ref:
        return Decision(False, "not_a_branch", outcome=ref)
    if branch != default_branch:
        return Decision(False, "not_default_branch", outcome=branch)
    if payload.get("deleted"):
        return Decision(False, "branch_deleted", outcome=branch)

    subject = _subject(payload.get("head_commit"))
    if _MERGE_COMMIT.match(subject) or _SQUASH_COMMIT.search(subject):
        return Decision(False, "pr_merge", outcome=branch)

    if not payload.get("commits"):
        # A force-push to the same tree, or a branch created from an existing
        # commit. Nothing new landed, so there is nothing to report.
        return Decision(False, "no_commits", outcome=branch)

    return Decision(True, "forwarded", outcome=branch)


def _decide_pull_request(payload: dict[str, Any]) -> Decision:
    """Announce a pull request opening and closing, whatever closed it.

    ``closed`` covers merges and abandonments alike; the payload's ``merged``
    flag is what tells them apart, and Discord's own embed says which. The
    noisy middle — synchronize, labeled, review_requested, edited — is dropped.
    """
    action = str(payload.get("action") or "")
    if action not in {"opened", "closed"}:
        return Decision(False, "action_not_tracked", outcome=action)
    if action == "closed" and (payload.get("pull_request") or {}).get("merged"):
        return Decision(True, "forwarded", outcome="merged")
    return Decision(True, "forwarded", outcome=action)


def _decide_issues(payload: dict[str, Any]) -> Decision:
    """Announce new issues only.

    Closing, labelling and commenting are all things you are already doing when
    they happen. Opening is the one that arrives from someone else.
    """
    action = str(payload.get("action") or "")
    if action != "opened":
        return Decision(False, "action_not_opened", outcome=action)
    return Decision(True, "forwarded", outcome=action)


def _decide_workflow_run(payload: dict[str, Any], default_branch: str) -> Decision:
    """Announce every completed run on the default branch, pass or fail.

    Successes are included deliberately: on the default branch a green run is
    the confirmation that what just landed builds, which is worth having when
    the branch is the one everything deploys from. Runs on other branches —
    every pull request's CI among them — are dropped, so a build that breaks
    before merge is not reported here.
    """
    run = payload.get("workflow_run")
    if not isinstance(run, dict):
        return Decision(False, "malformed")

    conclusion = run.get("conclusion")
    outcome = str(conclusion) if conclusion else None

    if payload.get("action") != "completed" or run.get("status") != "completed":
        # A null conclusion mid-run means "not yet", not "fine".
        return Decision(False, "not_completed", outcome=outcome)

    branch = str(run.get("head_branch") or "")
    if branch != default_branch:
        return Decision(False, "not_default_branch", outcome=outcome)

    return Decision(
        True,
        "forwarded",
        outcome=outcome or "unknown",
        message=build_workflow_message(payload),
    )


def decide(event: str, payload: dict[str, Any], default_branch: str) -> Decision:
    """Apply this event's policy, or drop an event with no policy at all."""
    if event == "release":
        return _decide_release(payload)
    if event == "push":
        return _decide_push(payload, default_branch)
    if event == "pull_request":
        return _decide_pull_request(payload)
    if event == "issues":
        return _decide_issues(payload)
    if event == "workflow_run":
        return _decide_workflow_run(payload, default_branch)
    return Decision(False, "event_not_tracked")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/webhooks/github",
    response_model=Envelope[NotificationResult],
    summary="GitHub org webhook → Discord (filtered)",
    description=(
        "Receives the org-level webhook for both GitHub orgs, verifies "
        "GitHub's X-Hub-Signature-256 over the raw body, and forwards only "
        "the deliveries that pass this service's per-event policy. "
        "Intentionally unauthenticated in the bearer-token sense: the "
        "shared-secret signature is the credential, because it is the only "
        "one GitHub can present."
    ),
    include_in_schema=False,
)
async def github_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Envelope[NotificationResult]:
    """Filter one GitHub delivery and forward it if the policy says so.

    Everything dropped still answers 200. A drop is a decision this route made,
    not an error GitHub should retry, and the delivery log in GitHub's UI reads
    far better when the only red entries are real ones.
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
        # The outer gate, so an org webhook subscribed to more than this
        # service handles can be narrowed without a deploy.
        return _result(settings, event=event, outcome=None, reason="event_not_enabled")

    repository: dict[str, Any] = payload.get("repository") or {}
    # The repository's own default branch, not a hardcoded "main": the two orgs
    # hold repos of different vintages, and a repo still on "master" should not
    # go silent because of a constant written here.
    default_branch = str(
        repository.get("default_branch") or settings.GITHUB_DEFAULT_BRANCH
    )

    decision = decide(event, payload, default_branch)
    repo_name = repository.get("full_name", "unknown")

    if not decision.forward:
        logger.debug(
            f"github delivery dropped repo={repo_name} event={event} "
            f"reason={decision.reason} outcome={decision.outcome} delivery={delivery}"
        )
        return _result(
            settings, event=event, outcome=decision.outcome, reason=decision.reason
        )

    logger.info(
        with_log_prefix(
            LOG_START,
            f"forwarding github event repo={repo_name} event={event} "
            f"outcome={decision.outcome} delivery={delivery}",
        )
    )

    if decision.message is not None:
        forwarded = await discord.send_message(
            settings=settings, payload=decision.message
        )
    else:
        forwarded = await discord.forward_github_event(
            settings=settings,
            raw_body=raw_body,
            event=event,
            delivery=delivery,
        )

    return _result(
        settings,
        event=event,
        outcome=decision.outcome,
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
