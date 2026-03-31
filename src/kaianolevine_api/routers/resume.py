from __future__ import annotations

import base64
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..config import Settings, get_settings

router = APIRouter()

_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign_jwt_rs256(private_key_pem: str, payload: dict[str, Any]) -> str:
    header = {"alg": "RS256", "typ": "JWT"}
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    key = serialization.load_pem_private_key(
        private_key_pem.encode(),
        password=None,
    )
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input.decode('utf-8')}.{_b64url(signature)}"


def _build_service_account_jwt(settings: Settings, now: int) -> str:
    if not settings.GOOGLE_CLIENT_EMAIL or not settings.GOOGLE_PRIVATE_KEY:
        msg = "Google service account credentials are not configured"
        raise HTTPException(
            status_code=502,
            detail={"code": "upstream_error", "message": msg},
        )
    payload = {
        "iss": settings.GOOGLE_CLIENT_EMAIL,
        "scope": "https://www.googleapis.com/auth/drive",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }
    return _sign_jwt_rs256(settings.GOOGLE_PRIVATE_KEY, payload)


async def _fetch_oauth_access_token(settings: Settings) -> None:
    now = int(time.time())
    assertion = _build_service_account_jwt(settings, now)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "upstream_error",
                "message": "Google OAuth token exchange failed",
            },
        )
    data = resp.json()
    access_token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    _token_cache["token"] = access_token
    _token_cache["expires_at"] = time.time() + expires_in


async def get_access_token(settings: Settings) -> str:
    """Return a valid Bearer token, refreshing from OAuth when near expiry."""
    now = time.time()
    token = _token_cache["token"]
    expires_at = float(_token_cache["expires_at"] or 0.0)
    if token and now < expires_at - 60:
        return str(token)
    await _fetch_oauth_access_token(settings)
    return str(_token_cache["token"])


def _safe_filename(name: str) -> str:
    return name.replace("\r", "").replace("\n", "").replace('"', "")


@router.get(
    "/resume",
    summary="Serve resume PDF",
    description=(
        "Streams the resume PDF from Google Drive. "
        "Supports iframe embedding on software.kaianolevine.com."
    ),
    response_model=None,
)
async def get_resume(settings: Settings = Depends(get_settings)) -> StreamingResponse:
    file_id = settings.RESUME_FILE_ID
    if not file_id:
        raise HTTPException(
            status_code=501,
            detail={
                "code": "not_configured",
                "message": "Resume file is not configured",
            },
        )

    bearer = await get_access_token(settings)
    headers = {"Authorization": f"Bearer {bearer}"}

    meta_url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        meta_resp = await client.get(
            meta_url,
            params={
                "supportsAllDrives": "true",
                "fields": "id,name,size,mimeType,webViewLink",
            },
            headers=headers,
        )

    if meta_resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail={"code": "upstream_error", "message": "Drive metadata fetch failed"},
        )

    meta = meta_resp.json()
    name = _safe_filename(meta.get("name") or "resume")
    mime = meta.get("mimeType") or "application/octet-stream"

    drive_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
    req = drive_client.build_request(
        "GET",
        meta_url,
        params={"alt": "media", "supportsAllDrives": "true"},
        headers=headers,
    )
    stream_http = await drive_client.send(req, stream=True)
    if stream_http.status_code != 200:
        await stream_http.aclose()
        await drive_client.aclose()
        raise HTTPException(
            status_code=502,
            detail={"code": "upstream_error", "message": "Drive file download failed"},
        )

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in stream_http.aiter_bytes():
                yield chunk
        finally:
            await stream_http.aclose()
            await drive_client.aclose()

    return StreamingResponse(
        body(),
        media_type=mime,
        headers={
            "Content-Disposition": f'inline; filename="{name}"',
            "Cache-Control": "public, max-age=3600",
            "Content-Security-Policy": "frame-ancestors https://software.kaianolevine.com",
        },
    )
