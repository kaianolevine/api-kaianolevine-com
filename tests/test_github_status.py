"""GET /v1/github/status — disclosure, caching, ordering, and degradation.

The disclosure tests are the load-bearing ones. `private_repos: aggregate`
is the difference between a portfolio page and a leak, and it is enforced in
one place — `services.github_dashboard.shape` — so these assert on the
serialized response body rather than on the shaping function: what matters
is that a private repo's name cannot be found anywhere in what goes over the
wire, by any path.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from kaianolevine_api.config import get_settings
from kaianolevine_api.services import github_dashboard as gh

GRAPHQL = "https://api.github.com/graphql"


def _repo(
    name: str,
    *,
    private: bool = False,
    archived: bool = False,
    fork: bool = False,
    rollup: str | None = "SUCCESS",
    prs: int = 0,
    issues: int = 0,
    pushed: str = "2026-09-01T00:00:00Z",
) -> dict:
    return {
        "name": name,
        "url": f"https://github.com/test-org/{name}",
        "description": f"{name} description",
        "isPrivate": private,
        "isArchived": archived,
        "isFork": fork,
        "pushedAt": pushed,
        "primaryLanguage": {"name": "Python"},
        "defaultBranchRef": {
            "name": "main",
            "target": {
                "committedDate": pushed,
                "statusCheckRollup": None if rollup is None else {"state": rollup},
            },
        },
        "pullRequests": {"totalCount": prs},
        "issues": {"totalCount": issues},
    }


def _page(nodes: list[dict]) -> dict:
    return {
        "data": {
            "organization": {
                "login": "test-org",
                "repositories": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": nodes,
                },
            }
        }
    }


@pytest.fixture
def dashboard(monkeypatch):
    """Configured token, one org, aggregate disclosure, empty cache."""
    settings = get_settings()
    monkeypatch.setattr(settings, "GITHUB_DASHBOARD_TOKEN", "test-token", raising=False)
    monkeypatch.setattr(settings, "GH_TOKEN", None, raising=False)
    monkeypatch.setattr(settings, "GITHUB_TOKEN", None, raising=False)
    monkeypatch.setattr(settings, "GITHUB_DASHBOARD_CACHE_TTL_SECS", 300, raising=False)

    def fake_config():
        return {
            "orgs": ["test-org"],
            "include": set(),
            "exclude": set(),
            "exclude_archived": True,
            "exclude_forks": True,
            "private_repos": "aggregate",
            "cache_ttl_seconds": 300,
        }

    monkeypatch.setattr(gh, "load_config", fake_config)
    gh.reset_cache()
    yield fake_config
    gh.reset_cache()


async def test_no_token_anywhere_is_not_configured(client, monkeypatch) -> None:
    settings = get_settings()
    for name in ("GITHUB_DASHBOARD_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.setattr(settings, name, None, raising=False)
    resp = await client.get("/v1/github/status")
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "not_configured"


def test_token_resolution_prefers_the_dedicated_name(monkeypatch) -> None:
    """The dedicated name wins, so narrowing the dashboard's rights is one
    variable to set — never something else to unset."""
    settings = get_settings()

    monkeypatch.setattr(settings, "GITHUB_DASHBOARD_TOKEN", "dedicated", raising=False)
    monkeypatch.setattr(settings, "GH_TOKEN", "gh", raising=False)
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "actions", raising=False)
    assert settings.github_dashboard_token == "dedicated"

    monkeypatch.setattr(settings, "GITHUB_DASHBOARD_TOKEN", None, raising=False)
    assert settings.github_dashboard_token == "gh"

    monkeypatch.setattr(settings, "GH_TOKEN", "   ", raising=False)
    assert settings.github_dashboard_token == "actions"

    monkeypatch.setattr(settings, "GITHUB_TOKEN", "", raising=False)
    assert settings.github_dashboard_token is None


@respx.mock
async def test_falls_back_to_gh_token(client, dashboard, monkeypatch) -> None:
    """No dedicated token set — the request still goes out, bearing GH_TOKEN."""
    settings = get_settings()
    monkeypatch.setattr(settings, "GITHUB_DASHBOARD_TOKEN", None, raising=False)
    monkeypatch.setattr(settings, "GH_TOKEN", "gh-token", raising=False)

    route = respx.post(GRAPHQL).mock(
        return_value=httpx.Response(200, json=_page([_repo("only")]))
    )
    resp = await client.get("/v1/github/status")

    assert resp.status_code == 200
    assert route.calls[0].request.headers["Authorization"] == "Bearer gh-token"


@respx.mock
async def test_private_repos_are_counted_but_never_named(client, dashboard) -> None:
    respx.post(GRAPHQL).mock(
        return_value=httpx.Response(
            200,
            json=_page(
                [
                    _repo("public-api", rollup="SUCCESS", prs=2, issues=5),
                    _repo(
                        "secret-client-work",
                        private=True,
                        rollup="FAILURE",
                        prs=1,
                        issues=3,
                    ),
                ]
            ),
        )
    )

    resp = await client.get("/v1/github/status")
    assert resp.status_code == 200
    body = resp.text
    data = resp.json()["data"]

    # Nothing anywhere in the response may name the private repo.
    assert "secret-client-work" not in body

    assert [r["name"] for r in data["repositories"]] == ["public-api"]

    private = data["orgs"][0]["private"]
    assert private["repo_count"] == 1
    assert private["builds"]["failure"] == 1
    assert private["open_pull_requests"] == 1
    assert private["open_issues"] == 3

    # Totals span both halves, so the headline is not quietly public-only.
    assert data["totals"]["repositories"] == 2
    assert data["totals"]["open_pull_requests"] == 3
    assert data["totals"]["open_issues"] == 8
    assert data["totals"]["builds"] == {
        "success": 1,
        "failure": 1,
        "error": 0,
        "pending": 0,
        "none": 0,
    }


@respx.mock
async def test_worst_build_first_and_no_checks_is_not_success(
    client, dashboard
) -> None:
    respx.post(GRAPHQL).mock(
        return_value=httpx.Response(
            200,
            json=_page(
                [
                    _repo("green", rollup="SUCCESS"),
                    _repo("unchecked", rollup=None),
                    _repo("broken", rollup="FAILURE"),
                    _repo("running", rollup="PENDING"),
                ]
            ),
        )
    )

    data = (await client.get("/v1/github/status")).json()["data"]
    assert [r["name"] for r in data["repositories"]] == [
        "broken",
        "running",
        "unchecked",
        "green",
    ]
    by_name = {r["name"]: r["build"] for r in data["repositories"]}
    assert by_name["unchecked"] == "none"


@respx.mock
async def test_archived_forks_and_excluded_repos_are_dropped(
    client, dashboard, monkeypatch
) -> None:
    cfg = dashboard()
    cfg["exclude"] = {"test-org/noisy"}
    monkeypatch.setattr(gh, "load_config", lambda: cfg)
    gh.reset_cache()

    respx.post(GRAPHQL).mock(
        return_value=httpx.Response(
            200,
            json=_page(
                [
                    _repo("keeper"),
                    _repo("old", archived=True),
                    _repo("someone-elses", fork=True),
                    _repo("noisy"),
                ]
            ),
        )
    )

    data = (await client.get("/v1/github/status")).json()["data"]
    assert [r["name"] for r in data["repositories"]] == ["keeper"]
    assert data["totals"]["repositories"] == 1


@respx.mock
async def test_second_request_inside_ttl_does_not_call_github(
    client, dashboard
) -> None:
    route = respx.post(GRAPHQL).mock(
        return_value=httpx.Response(200, json=_page([_repo("only")]))
    )

    first = await client.get("/v1/github/status")
    second = await client.get("/v1/github/status")

    assert route.call_count == 1
    assert first.json()["data"]["fetched_at"] == second.json()["data"]["fetched_at"]
    assert second.json()["data"]["stale"] is False


@respx.mock
async def test_github_failure_serves_the_previous_snapshot_marked_stale(
    client, dashboard, monkeypatch
) -> None:
    route = respx.post(GRAPHQL).mock(
        return_value=httpx.Response(200, json=_page([_repo("only")]))
    )
    good = (await client.get("/v1/github/status")).json()["data"]

    # Expire the snapshot, then break GitHub.
    monkeypatch.setattr(gh, "cache_ttl", lambda _settings: 0)
    route.mock(return_value=httpx.Response(500, json={"message": "boom"}))

    resp = await client.get("/v1/github/status")
    assert resp.status_code == 200
    stale = resp.json()["data"]
    assert stale["stale"] is True
    assert stale["fetched_at"] == good["fetched_at"]
    assert resp.headers["cache-control"] == "public, max-age=60"


@respx.mock
async def test_github_failure_with_no_snapshot_is_upstream_error(
    client, dashboard
) -> None:
    respx.post(GRAPHQL).mock(return_value=httpx.Response(500, json={"message": "boom"}))
    resp = await client.get("/v1/github/status")
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "upstream_error"


@respx.mock
async def test_graphql_errors_in_a_200_are_treated_as_failure(
    client, dashboard
) -> None:
    respx.post(GRAPHQL).mock(
        return_value=httpx.Response(
            200, json={"data": {"organization": None}, "errors": [{"message": "nope"}]}
        )
    )
    resp = await client.get("/v1/github/status")
    assert resp.status_code == 502


def test_committed_config_is_valid_and_names_at_least_one_org() -> None:
    """The shipped YAML parses and is not empty — a typo here is a blank board."""
    gh.load_config.cache_clear()
    cfg = gh.load_config()
    assert cfg["orgs"], "config_data/github_dashboard.yaml lists no orgs"
    assert cfg["private_repos"] in {"aggregate", "hidden", "full"}


# ── Degradation when one org of several cannot be read ────────────────────
#
# The failure this covers actually happened: a second org was added to the
# committed config, the deployed token could not see it, and the board went
# to 502 — taking the readable org down with it. One org's problem must cost
# that org and nothing else.


def _two_orgs(monkeypatch):
    cfg = {
        "orgs": ["readable-org", "invisible-org"],
        "include": set(),
        "exclude": set(),
        "exclude_archived": True,
        "exclude_forks": True,
        "private_repos": "aggregate",
        "cache_ttl_seconds": 300,
    }
    monkeypatch.setattr(gh, "load_config", lambda: cfg)
    gh.reset_cache()
    return cfg


def _login_of(request) -> str:
    import json

    return json.loads(request.content)["variables"]["login"]


@respx.mock
async def test_one_unreadable_org_does_not_take_down_the_others(
    client, dashboard, monkeypatch
) -> None:
    _two_orgs(monkeypatch)

    def route(request):
        if _login_of(request) == "readable-org":
            return httpx.Response(200, json=_page([_repo("visible", rollup="SUCCESS")]))
        # GitHub answers an org it cannot resolve or cannot show you the
        # same way: data.organization is null.
        return httpx.Response(200, json={"data": {"organization": None}})

    respx.post(GRAPHQL).mock(side_effect=route)

    resp = await client.get("/v1/github/status")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert [r["name"] for r in data["repositories"]] == ["visible"]
    assert data["unavailable_orgs"] == [
        {"login": "invisible-org", "reason": "not_found_or_no_access"}
    ]
    # The readable org's numbers are still whole.
    assert data["totals"]["repositories"] == 1


@respx.mock
async def test_every_org_failing_is_still_an_upstream_error(
    client, dashboard, monkeypatch
) -> None:
    """A bad token fails every org, and there is nothing truthful to render.

    The 502 still carries why. A single-org deployment can never reach the
    partial-success path, so without this the most likely misconfiguration
    would be the least diagnosable one.
    """
    _two_orgs(monkeypatch)
    respx.post(GRAPHQL).mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )

    resp = await client.get("/v1/github/status")
    assert resp.status_code == 502
    error = resp.json()["error"]
    assert error["code"] == "upstream_error"
    assert error["details"]["orgs"] == [
        {"login": "readable-org", "reason": "unauthorized"},
        {"login": "invisible-org", "reason": "unauthorized"},
    ]


@respx.mock
async def test_single_org_failure_names_the_org_and_reason(client, dashboard) -> None:
    """The shipped config has exactly one org — this is the real shape."""
    respx.post(GRAPHQL).mock(
        return_value=httpx.Response(200, json={"data": {"organization": None}})
    )

    resp = await client.get("/v1/github/status")
    assert resp.status_code == 502
    assert resp.json()["error"]["details"]["orgs"] == [
        {"login": "test-org", "reason": "not_found_or_no_access"}
    ]


@respx.mock
async def test_unavailable_reason_never_leaks_github_error_text(
    client, dashboard, monkeypatch
) -> None:
    """The route is public: the category ships, the message stays in the logs."""
    _two_orgs(monkeypatch)
    secret = "Could not resolve to an Organization with the login of 'invisible-org'"

    def route(request):
        if _login_of(request) == "readable-org":
            return httpx.Response(200, json=_page([_repo("visible")]))
        return httpx.Response(
            200, json={"data": {"organization": None}, "errors": [{"message": secret}]}
        )

    respx.post(GRAPHQL).mock(side_effect=route)

    resp = await client.get("/v1/github/status")
    assert resp.status_code == 200
    assert secret not in resp.text
    assert resp.json()["data"]["unavailable_orgs"][0]["reason"] == (
        "not_found_or_no_access"
    )
