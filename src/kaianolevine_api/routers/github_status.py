"""Public repo status board — GET /v1/github/status.

Thin by design. Everything that decides *what* a stranger may read lives in
``services.github_dashboard`` and the YAML beside it; this module's whole
job is caching semantics on the wire and the two failure codes.

**No auth.** The response is the same for every caller and contains only
what the committed config permits on a public page. Putting a credential in
front of it would move the token from Railway into a static bundle, which is
the problem the route exists to avoid.

**Two distinct failures, deliberately.** No usable token is 501
``not_configured`` — the deployment is incomplete, and an empty board would
misread as a fleet with nothing in it. GitHub being unreachable with no
snapshot in hand is 502 ``upstream_error``. The site hides the panel on
either, but the distinction is what the logs need.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from ..config import Settings, get_settings
from ..schemas import Envelope, GithubStatus, api_error, success_envelope
from ..services.github_dashboard import GithubUnavailable, get_status

router = APIRouter()

#: How long a browser may reuse a stale snapshot. Short, so a visitor who
#: arrives during a GitHub outage sees the recovery rather than the outage.
STALE_MAX_AGE_SECS = 60


@router.get(
    "/github/status",
    response_model=Envelope[GithubStatus],
    summary="Repository status board",
    description=(
        "Build state, open pull requests and open issues across the configured "
        "GitHub organizations. Public repositories are listed individually; "
        "private repositories are counted per organization and never named. "
        "Served from a cached snapshot — see `fetched_at` and `stale`."
    ),
)
async def github_status(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> Envelope[GithubStatus]:
    """Return the cached repo status board in the standard envelope."""
    if not settings.github_dashboard_token:
        raise api_error(
            501,
            "not_configured",
            "GitHub dashboard token is not configured",
        )

    try:
        payload = await get_status(settings)
    except GithubUnavailable:
        raise api_error(502, "upstream_error", "GitHub status is unavailable") from None

    max_age = STALE_MAX_AGE_SECS if payload.stale else payload.cache_ttl_seconds
    response.headers["Cache-Control"] = f"public, max-age={max_age}"

    return success_envelope(
        payload,
        count=len(payload.repositories),
        total=payload.totals.repositories,
        version=settings.API_VERSION,
    )
