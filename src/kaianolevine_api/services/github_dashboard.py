"""GitHub repo status for the public dashboard — the one place GitHub is read.

**Why a proxy and not a browser fetch.** The page is static HTML on
Cloudflare Pages. A browser calling GitHub directly would either need an
unauthenticated 60-requests-per-hour budget shared by every visitor, or a
token shipped in the bundle. Reading GitHub here keeps the token on
Railway and turns N visitors into one upstream call per TTL.

**Why GraphQL and not REST.** The board needs, per repo: the default
branch's head commit, that commit's check rollup, an open-PR count and an
open-issue count. In REST that is roughly four requests per repo — a
hundred-odd for a two-org fleet, every refresh. In GraphQL it is one
request per fifty repos. The rate limit stops being something to think
about, which is the point: a portfolio panel that burns a budget is a
liability, not a demonstration.

**Private repos are counted, never named.** ``private_repos: aggregate``
in ``config_data/github_dashboard.yaml`` is the default and the reason
this module shapes its output rather than forwarding GitHub's. A private
repo contributes to its org's counts and nothing else — no name, no URL,
no description, no branch, no titles. The redaction happens here, before
the payload exists, so no route, schema or template can leak what was
never assembled.

**Staleness is reported, not hidden.** When GitHub fails and a previous
snapshot is in hand, the snapshot is served with ``stale`` true and its
original ``fetched_at``. A board that silently shows five-hour-old builds
as current is worse than one that says how old it is. With no snapshot to
fall back on the error propagates and the panel hides itself.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import yaml
from mini_app_polis.logger import (
    LOG_FAILURE,
    LOG_WARNING,
    get_logger,
    with_log_prefix,
)

from ..config import Settings
from ..schemas import (
    GithubBuildCounts,
    GithubOrgError,
    GithubOrgSummary,
    GithubPrivateSummary,
    GithubRepoStatus,
    GithubStatus,
    GithubTotals,
)

logger = get_logger()

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

#: Where the committed configuration lives, relative to this package.
CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "config_data" / "github_dashboard.yaml"
)

#: Repos fetched per GraphQL page. GitHub's ceiling is 100; fifty keeps the
#: query's node cost well inside the limit even for orgs full of large repos.
PAGE_SIZE = 50

#: Guard against an unbounded loop if GitHub ever returns a cursor that does
#: not advance. Twenty pages is a thousand repos — far past this fleet.
MAX_PAGES = 20

#: GitHub's ``StatusState`` mapped onto the vocabulary the page renders.
#: ``EXPECTED`` means a check has been declared but has not reported, which
#: is a pending build from a reader's point of view. A null rollup means the
#: commit has no checks at all, which is a distinct and interesting state on
#: a board about engineering standards — it is not a success.
_ROLLUP_STATES: dict[str | None, str] = {
    "SUCCESS": "success",
    "FAILURE": "failure",
    "ERROR": "error",
    "PENDING": "pending",
    "EXPECTED": "pending",
    None: "none",
}

#: Worst first. The board exists to surface what is broken, so ordering is
#: part of the payload rather than a choice each client re-makes.
_BUILD_ORDER = {"failure": 0, "error": 1, "pending": 2, "none": 3, "success": 4}

ORG_QUERY = """
query($login: String!, $cursor: String, $pageSize: Int!) {
  organization(login: $login) {
    login
    repositories(
      first: $pageSize
      after: $cursor
      ownerAffiliations: OWNER
      orderBy: { field: PUSHED_AT, direction: DESC }
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        url
        description
        isPrivate
        isArchived
        isFork
        pushedAt
        primaryLanguage { name }
        defaultBranchRef {
          name
          target {
            ... on Commit {
              committedDate
              statusCheckRollup { state }
            }
          }
        }
        pullRequests(states: OPEN) { totalCount }
        issues(states: OPEN) { totalCount }
        refs(refPrefix: "refs/heads/", first: 1) { totalCount }
      }
    }
  }
}
"""


class GithubUnavailable(RuntimeError):
    """GitHub could not be read at all and no previous snapshot exists.

    Carries the per-org reasons so the 502 can say *why*. Without this the
    diagnostic only works when at least one org succeeds — and a fleet
    configured with a single org can never be in that state, so the one
    deployment most likely to be misconfigured would be the one that told
    you the least.
    """

    def __init__(self, message: str, orgs: list[GithubOrgError] | None = None) -> None:
        super().__init__(message)
        self.orgs = list(orgs or [])


class OrgUnavailable(RuntimeError):
    """One organization could not be read. Carries a public-safe reason.

    Separate from GithubUnavailable because the two are different events. A
    fleet spans several orgs; one of them being unreadable — a login typo, a
    fine-grained token never authorized for that org, a private org the
    token is not a member of — should cost that org's rows and nothing
    else. Failing the whole board on it, which is what the first version of
    this module did, turns a one-line config mistake into a blank page and
    gives the reader no way to tell the two apart.
    """

    def __init__(self, login: str, reason: str, detail: str) -> None:
        super().__init__(f"{login}: {reason} ({detail})")
        self.login = login
        self.reason = reason
        self.detail = detail


# ── Configuration ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    """Read and normalize the committed dashboard configuration."""
    raw = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    orgs = [str(o).strip() for o in (raw.get("orgs") or []) if str(o).strip()]
    disclosure = str(raw.get("private_repos") or "aggregate").strip().lower()
    if disclosure not in {"aggregate", "hidden", "full"}:
        logger.warning(
            with_log_prefix(
                LOG_WARNING,
                f"unknown private_repos value {disclosure!r}; falling back to aggregate",
            )
        )
        disclosure = "aggregate"
    return {
        "orgs": orgs,
        "include": {str(x).strip().lower() for x in (raw.get("include") or [])},
        "exclude": {str(x).strip().lower() for x in (raw.get("exclude") or [])},
        "exclude_archived": bool(raw.get("exclude_archived", True)),
        "exclude_forks": bool(raw.get("exclude_forks", True)),
        "private_repos": disclosure,
        "cache_ttl_seconds": int(raw.get("cache_ttl_seconds", 300)),
    }


def cache_ttl(settings: Settings) -> int:
    """TTL in seconds — the environment override, else the committed value."""
    override = settings.GITHUB_DASHBOARD_CACHE_TTL_SECS
    if override is not None and override > 0:
        return int(override)
    return max(0, load_config()["cache_ttl_seconds"])


# ── Fetch ────────────────────────────────────────────────────────────────


def _reason_for_status(response: httpx.Response) -> str:
    """Map an HTTP failure onto a public-safe reason."""
    code = response.status_code
    if code in (401, 403):
        # 403 is GitHub's secondary rate limit as well as its forbidden, and
        # the two are told apart by a header rather than the status.
        if "rate limit" in (response.text or "").lower():
            return "rate_limited"
        return "unauthorized"
    if code == 404:
        return "not_found_or_no_access"
    if code == 429:
        return "rate_limited"
    return "unreachable"


def _describe_graphql_errors(errors: list[dict[str, Any]]) -> str:
    """Summarize GraphQL errors by the FIELD each one failed on.

    A permission gap arrives as one error per offending field per repo —
    dozens of identical messages that say what went wrong and never where.
    The `path` is the part that names the missing permission: `issues` means
    Issues, `pullRequests` means Pull requests, `statusCheckRollup` means
    Checks and Commit statuses. Logging the messages alone, which is what
    this did first, turns a one-line diagnosis into a guess.
    """
    fields = sorted(
        {
            str((error.get("path") or ["<no path>"])[-1])
            for error in errors
            if isinstance(error, dict)
        }
    )
    sample = str((errors[0] or {}).get("message", "")) if errors else ""
    return f"{len(errors)} error(s) on field(s): {', '.join(fields)} — {sample}"


def _reason_for_graphql(messages: str) -> str:
    """Map GraphQL error text onto a public-safe reason."""
    lowered = messages.lower()
    if "rate limit" in lowered:
        return "rate_limited"
    if "bad credentials" in lowered or "credentials" in lowered:
        return "unauthorized"
    # A fine-grained token missing one permission answers with a 200 and
    # "Resource not accessible by personal access token" against the field
    # it could not read — most often statusCheckRollup. That is a rights
    # problem, not an outage, and saying so is what makes it fixable.
    if "not accessible" in lowered:
        return "unauthorized"
    if "could not resolve" in lowered or "not resolve to" in lowered:
        return "not_found_or_no_access"
    return "unreachable"


async def _query_org(
    client: httpx.AsyncClient, login: str, token: str
) -> list[dict[str, Any]]:
    """Return every repository node for one org, following pagination."""
    nodes: list[dict[str, Any]] = []
    cursor: str | None = None

    for _ in range(MAX_PAGES):
        try:
            resp = await client.post(
                GITHUB_GRAPHQL_URL,
                json={
                    "query": ORG_QUERY,
                    "variables": {
                        "login": login,
                        "cursor": cursor,
                        "pageSize": PAGE_SIZE,
                    },
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "User-Agent": "kaianolevine-api-github-dashboard",
                },
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise OrgUnavailable(
                login,
                _reason_for_status(exc.response),
                f"HTTP {exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            raise OrgUnavailable(login, "unreachable", type(exc).__name__) from exc

        body = resp.json()

        # GraphQL reports partial failures in a 200. Treat them as failures
        # for this org rather than silently publishing a short board.
        if body.get("errors"):
            raise OrgUnavailable(
                login,
                _reason_for_graphql(
                    " ".join(str(e.get("message", "")) for e in body["errors"])
                ),
                _describe_graphql_errors(body["errors"]),
            )

        org = (body.get("data") or {}).get("organization")
        if not org:
            # GitHub answers a login it cannot resolve *or* cannot show you
            # the same way: a null organization. The two are indistinguishable
            # from here, which is why the reason covers both.
            raise OrgUnavailable(
                login, "not_found_or_no_access", "null organization in response"
            )

        page = org.get("repositories") or {}
        nodes.extend(n for n in (page.get("nodes") or []) if n)

        info = page.get("pageInfo") or {}
        if not info.get("hasNextPage"):
            return nodes
        next_cursor = info.get("endCursor")
        if not next_cursor or next_cursor == cursor:
            return nodes
        cursor = next_cursor

    logger.warning(
        with_log_prefix(
            LOG_WARNING, f"{login}: stopped paginating at {MAX_PAGES} pages"
        )
    )
    return nodes


# ── Shaping ──────────────────────────────────────────────────────────────


def _keep(node: dict[str, Any], login: str, cfg: dict[str, Any]) -> bool:
    """Apply the committed include/exclude/archived/fork filters."""
    slug = f"{login}/{node.get('name', '')}".lower()
    if cfg["include"] and slug not in cfg["include"]:
        return False
    if slug in cfg["exclude"]:
        return False
    if cfg["exclude_archived"] and node.get("isArchived"):
        return False
    if cfg["exclude_forks"] and node.get("isFork"):
        return False
    return True


def _build_state(node: dict[str, Any]) -> str:
    """Map the default branch head's check rollup onto our vocabulary."""
    ref = node.get("defaultBranchRef") or {}
    target = ref.get("target") or {}
    rollup = target.get("statusCheckRollup") or {}
    return _ROLLUP_STATES.get(rollup.get("state"), "none")


def _parse_ts(value: Any) -> dt.datetime | None:
    """Parse a GitHub ISO-8601 timestamp, tolerating the trailing Z."""
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _repo_status(node: dict[str, Any], login: str) -> GithubRepoStatus:
    ref = node.get("defaultBranchRef") or {}
    language = node.get("primaryLanguage") or {}
    return GithubRepoStatus(
        org=login,
        name=str(node.get("name") or ""),
        url=str(node.get("url") or ""),
        description=node.get("description"),
        language=language.get("name"),
        default_branch=ref.get("name"),
        build=_build_state(node),
        open_pull_requests=int((node.get("pullRequests") or {}).get("totalCount", 0)),
        open_issues=int((node.get("issues") or {}).get("totalCount", 0)),
        branches=int((node.get("refs") or {}).get("totalCount", 0)),
        pushed_at=_parse_ts(node.get("pushedAt")),
    )


def _counts(states: list[str]) -> GithubBuildCounts:
    return GithubBuildCounts(
        success=states.count("success"),
        failure=states.count("failure"),
        error=states.count("error"),
        pending=states.count("pending"),
        none=states.count("none"),
    )


def _sort_key(repo: GithubRepoStatus) -> tuple[int, float]:
    """Worst build first, then most recently pushed."""
    recency = repo.pushed_at.timestamp() if repo.pushed_at else 0.0
    return (_BUILD_ORDER.get(repo.build, 9), -recency)


def shape(
    per_org: dict[str, list[dict[str, Any]]],
    cfg: dict[str, Any],
    *,
    fetched_at: dt.datetime,
    ttl: int,
    unavailable: list[GithubOrgError] | None = None,
) -> GithubStatus:
    """Turn raw GitHub nodes into the payload the public page receives.

    Private repos are reduced to counts here, or dropped, according to
    ``private_repos``. Nothing downstream of this function has the names.
    """
    disclosure = cfg["private_repos"]
    listed: list[GithubRepoStatus] = []
    orgs: list[GithubOrgSummary] = []

    for login, nodes in per_org.items():
        kept = [n for n in nodes if _keep(n, login, cfg)]
        public = [n for n in kept if not n.get("isPrivate")]
        private = [n for n in kept if n.get("isPrivate")]

        listed.extend(_repo_status(n, login) for n in public)

        private_summary: GithubPrivateSummary | None = None
        if disclosure == "full":
            listed.extend(_repo_status(n, login) for n in private)
        elif disclosure == "aggregate" and private:
            private_summary = GithubPrivateSummary(
                repo_count=len(private),
                builds=_counts([_build_state(n) for n in private]),
                open_pull_requests=sum(
                    int((n.get("pullRequests") or {}).get("totalCount", 0))
                    for n in private
                ),
                open_issues=sum(
                    int((n.get("issues") or {}).get("totalCount", 0)) for n in private
                ),
                branches=sum(
                    int((n.get("refs") or {}).get("totalCount", 0)) for n in private
                ),
            )

        orgs.append(
            GithubOrgSummary(
                login=login,
                listed_repo_count=len(public)
                + (len(private) if disclosure == "full" else 0),
                private=private_summary,
            )
        )

    listed.sort(key=_sort_key)

    # Totals span everything counted, listed or aggregated, so the headline
    # numbers do not quietly describe only the public half.
    total_repos = len(listed) + sum(o.private.repo_count for o in orgs if o.private)
    total_prs = sum(r.open_pull_requests for r in listed) + sum(
        o.private.open_pull_requests for o in orgs if o.private
    )
    total_issues = sum(r.open_issues for r in listed) + sum(
        o.private.open_issues for o in orgs if o.private
    )
    total_branches = sum(r.branches for r in listed) + sum(
        o.private.branches for o in orgs if o.private
    )
    listed_counts = _counts([r.build for r in listed])
    builds = GithubBuildCounts(
        success=listed_counts.success
        + sum(o.private.builds.success for o in orgs if o.private),
        failure=listed_counts.failure
        + sum(o.private.builds.failure for o in orgs if o.private),
        error=listed_counts.error
        + sum(o.private.builds.error for o in orgs if o.private),
        pending=listed_counts.pending
        + sum(o.private.builds.pending for o in orgs if o.private),
        none=listed_counts.none + sum(o.private.builds.none for o in orgs if o.private),
    )

    return GithubStatus(
        fetched_at=fetched_at,
        stale=False,
        cache_ttl_seconds=ttl,
        private_disclosure=disclosure,
        orgs=orgs,
        repositories=listed,
        unavailable_orgs=list(unavailable or []),
        totals=GithubTotals(
            repositories=total_repos,
            open_pull_requests=total_prs,
            open_issues=total_issues,
            branches=total_branches,
            builds=builds,
        ),
    )


# ── Cache ────────────────────────────────────────────────────────────────

_snapshot: dict[str, Any] = {"payload": None, "monotonic": 0.0}
_refresh_lock = asyncio.Lock()


def reset_cache() -> None:
    """Drop the cached snapshot. Tests call this; nothing else should."""
    _snapshot["payload"] = None
    _snapshot["monotonic"] = 0.0
    # Defensive: tests substitute load_config with a plain callable.
    clear = getattr(load_config, "cache_clear", None)
    if clear is not None:
        clear()


async def _refresh(settings: Settings, cfg: dict[str, Any], ttl: int) -> GithubStatus:
    token = settings.github_dashboard_token or ""
    per_org: dict[str, list[dict[str, Any]]] = {}
    timeout = httpx.Timeout(settings.HTTP_CLIENT_TIMEOUT_SECS or 10.0)

    unavailable: list[GithubOrgError] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for login in cfg["orgs"]:
            try:
                per_org[login] = await _query_org(client, login, token)
            except OrgUnavailable as exc:
                # One org's problem costs that org and nothing else. The
                # detail goes to the logs; the payload carries the category.
                logger.warning(
                    with_log_prefix(
                        LOG_WARNING,
                        f"github dashboard: skipping org {exc.login} — {exc.reason}: {exc.detail}",
                    )
                )
                unavailable.append(GithubOrgError(login=exc.login, reason=exc.reason))

    # Every configured org failing is a different event from one failing: it
    # is almost always the token rather than the config, and there is nothing
    # truthful to render. Let it fall through to the stale snapshot, or to 502.
    if cfg["orgs"] and not per_org:
        reasons = ", ".join(sorted({e.reason for e in unavailable}))
        raise GithubUnavailable(
            f"no organization could be read ({reasons})", unavailable
        )

    return shape(
        per_org,
        cfg,
        fetched_at=dt.datetime.now(dt.UTC),
        ttl=ttl,
        unavailable=unavailable,
    )


async def get_status(settings: Settings) -> GithubStatus:
    """Return the dashboard payload, refreshing from GitHub past the TTL.

    Concurrent callers past the TTL take the lock one at a time and the
    later ones find the fresh snapshot already there, so a burst of
    visitors is still one upstream call.
    """
    cfg = load_config()
    ttl = cache_ttl(settings)
    now = time.monotonic()

    cached: GithubStatus | None = _snapshot["payload"]
    if cached is not None and now - float(_snapshot["monotonic"]) < ttl:
        return cached

    async with _refresh_lock:
        now = time.monotonic()
        cached = _snapshot["payload"]
        if cached is not None and now - float(_snapshot["monotonic"]) < ttl:
            return cached
        try:
            payload = await _refresh(settings, cfg, ttl)
        except Exception as exc:
            if cached is not None:
                logger.warning(
                    with_log_prefix(
                        LOG_WARNING,
                        f"GitHub refresh failed ({type(exc).__name__}); serving stale snapshot",
                    )
                )
                return cached.model_copy(update={"stale": True})
            logger.error(
                with_log_prefix(
                    LOG_FAILURE, f"GitHub refresh failed with no snapshot: {exc}"
                )
            )
            # Already the right exception, and it knows which orgs failed.
            # Re-wrapping it would throw that away.
            if isinstance(exc, GithubUnavailable):
                raise
            raise GithubUnavailable(str(exc)) from exc

        _snapshot["payload"] = payload
        _snapshot["monotonic"] = time.monotonic()
        return payload
