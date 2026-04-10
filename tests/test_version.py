from __future__ import annotations


async def test_version_endpoint_returns_package_version(client) -> None:
    resp = await client.get("/version")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    # pyproject uses full semver (e.g. 1.13.2)
    assert isinstance(data["version"], str)
    assert "." in data["version"]


async def test_root_redirects_to_docs(client) -> None:
    resp = await client.get("/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/docs"


async def test_openapi_version_matches_version_endpoint(client) -> None:
    version_resp = await client.get("/version")
    openapi_resp = await client.get("/openapi.json")
    assert version_resp.status_code == 200
    assert openapi_resp.status_code == 200
    assert version_resp.json()["version"] == openapi_resp.json()["info"]["version"]
