from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest
import respx
from httpx import AsyncClient, Response

from kaianolevine_api.config import get_settings


@pytest.fixture(autouse=True)
def clear_resume_token_cache() -> Iterator[None]:
    from kaianolevine_api.routers import resume as resume_mod

    resume_mod._token_cache["token"] = None
    resume_mod._token_cache["expires_at"] = 0.0
    yield
    resume_mod._token_cache["token"] = None
    resume_mod._token_cache["expires_at"] = 0.0


@pytest.mark.asyncio
async def test_resume_501_when_resume_file_id_missing(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    monkeypatch.delenv("RESUME_FILE_ID", raising=False)
    get_settings.cache_clear()
    resp = await client.get("/v1/resume")
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "not_configured"
    get_settings.cache_clear()


@pytest.mark.asyncio
@respx.mock
async def test_resume_200_headers_and_streaming_body(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    monkeypatch.setenv("RESUME_FILE_ID", "file-abc")
    monkeypatch.setenv("GOOGLE_CLIENT_EMAIL", "svc@proj.iam.gserviceaccount.com")
    monkeypatch.setenv("GOOGLE_PRIVATE_KEY", "dummy")
    get_settings.cache_clear()

    file_id = "file-abc"
    meta_url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=Response(
            200, json={"access_token": "test-token", "expires_in": 3600}
        )
    )
    respx.get(meta_url).mock(
        side_effect=[
            Response(
                200,
                json={
                    "id": "fid",
                    "name": 'Re"sume\r\n.pdf',
                    "mimeType": "application/pdf",
                    "size": "10",
                    "webViewLink": "https://example.com",
                },
            ),
            Response(
                200, content=b"%PDF-1.4", headers={"Content-Type": "application/pdf"}
            ),
        ]
    )
    with patch(
        "kaianolevine_api.routers.resume._build_service_account_jwt",
        return_value="jwt",
    ):
        resp = await client.get("/v1/resume")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.headers["cache-control"] == "public, max-age=3600"
    assert (
        resp.headers["content-security-policy"]
        == "frame-ancestors https://software.kaianolevine.com"
    )
    assert resp.headers["content-disposition"] == 'inline; filename="Resume.pdf"'
    lowered = {k.lower() for k in resp.headers.keys()}
    assert "x-frame-options" not in lowered
    assert resp.content == b"%PDF-1.4"
    get_settings.cache_clear()


@pytest.mark.asyncio
@respx.mock
async def test_resume_502_when_drive_metadata_fails(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    monkeypatch.setenv("RESUME_FILE_ID", "file-abc")
    monkeypatch.setenv("GOOGLE_CLIENT_EMAIL", "svc@proj.iam.gserviceaccount.com")
    monkeypatch.setenv("GOOGLE_PRIVATE_KEY", "dummy")
    get_settings.cache_clear()

    file_id = "file-abc"
    meta_url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=Response(
            200, json={"access_token": "test-token", "expires_in": 3600}
        )
    )
    respx.get(meta_url).mock(return_value=Response(404, json={}))
    with patch(
        "kaianolevine_api.routers.resume._build_service_account_jwt",
        return_value="jwt",
    ):
        resp = await client.get("/v1/resume")

    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "upstream_error"
    get_settings.cache_clear()


@pytest.mark.asyncio
@respx.mock
async def test_resume_502_when_drive_download_fails(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    monkeypatch.setenv("RESUME_FILE_ID", "file-abc")
    monkeypatch.setenv("GOOGLE_CLIENT_EMAIL", "svc@proj.iam.gserviceaccount.com")
    monkeypatch.setenv("GOOGLE_PRIVATE_KEY", "dummy")
    get_settings.cache_clear()

    file_id = "file-abc"
    meta_url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=Response(
            200, json={"access_token": "test-token", "expires_in": 3600}
        )
    )
    respx.get(meta_url).mock(
        side_effect=[
            Response(
                200,
                json={
                    "id": "fid",
                    "name": 'Re"sume\r\n.pdf',
                    "mimeType": "application/pdf",
                    "size": "10",
                    "webViewLink": "https://example.com",
                },
            ),
            Response(403, json={}),
        ]
    )
    with patch(
        "kaianolevine_api.routers.resume._build_service_account_jwt",
        return_value="jwt",
    ):
        resp = await client.get("/v1/resume")

    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "upstream_error"
    get_settings.cache_clear()
