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


async def test_missing_token_is_not_configured(client, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "GITHUB_DASHBOARD_TOKEN", None, raising=False)
    resp = await client.get("/v1/github/status")
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "not_configured"


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
