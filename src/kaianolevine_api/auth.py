"""Authentication — Clerk JWT verification (Project Keystone Phase 3).

All requests must carry ``Authorization: Bearer <jwt>`` where the JWT is
either a Clerk session token (human user) or a Clerk M2M JWT (cog/service).
Both are RS256 tokens verified locally via JWKS — no network call to Clerk.

Required env vars:
  CLERK_JWKS_URL — e.g. https://clerk.kaianolevine.com/.well-known/jwks.json
  CLERK_ISSUER   — e.g. https://clerk.kaianolevine.com
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import jwt
from fastapi import Depends, Header
from jwt import PyJWK
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings
from .database import get_db_session
from .models import WcsUserProfile
from .schemas import api_error

# JWKS document cache: url -> (monotonic_expiry, jwks_json). TTL 5 minutes.
_jwks_doc_cache: dict[str, tuple[float, dict[str, Any]]] = {}


async def _fetch_jwks_document(jwks_url: str) -> dict[str, Any]:
    """Fetch JWKS JSON with httpx; reuse cached document for 5 minutes."""
    import httpx

    now = time.monotonic()
    hit = _jwks_doc_cache.get(jwks_url)
    if hit is not None:
        expires_at, doc = hit
        if now < expires_at:
            return doc

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        doc = resp.json()

    _jwks_doc_cache[jwks_url] = (now + 300.0, doc)
    return doc


def _decode_clerk_jwt_sync(
    token: str, settings: Settings, jwks_doc: dict[str, Any]
) -> str | None:
    """Verify RS256 JWT against a JWKS document; return ``sub`` or None."""
    if not settings.CLERK_ISSUER:
        return None
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            return None

        keys = jwks_doc.get("keys")
        if not isinstance(keys, list):
            return None

        jwk_dict: dict[str, Any] | None = None
        for key in keys:
            if isinstance(key, dict) and key.get("kid") == kid:
                jwk_dict = key
                break
        if jwk_dict is None:
            return None

        signing_key = PyJWK.from_dict(jwk_dict)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.CLERK_ISSUER,
            options={"verify_aud": False},
        )
        sub = payload.get("sub")
        return str(sub) if sub is not None else None
    except Exception:
        return None


async def verify_clerk_jwt(token: str, settings: Settings) -> str | None:
    """
    Verify a Clerk RS256 JWT (session token or M2M JWT).
    Returns the ``sub`` claim on success, or None on failure.
    """
    if not settings.CLERK_JWKS_URL or not settings.CLERK_ISSUER:
        return None
    try:
        jwks_doc = await _fetch_jwks_document(settings.CLERK_JWKS_URL)
    except Exception:
        return None
    return await asyncio.to_thread(_decode_clerk_jwt_sync, token, settings, jwks_doc)


async def get_current_owner(
    authorization: str | None = Header(default=None, alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Resolves owner identity from a Clerk JWT.
    Raises 401 if the token is missing or invalid.
    """
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            sub = await verify_clerk_jwt(token, settings)
            if sub:
                return sub

    raise api_error(401, "unauthorized", "Valid Bearer token required")


async def require_wcs_admin(
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> str:
    """Ensures the caller is a WCS admin."""
    result = await session.execute(
        select(WcsUserProfile).where(WcsUserProfile.user_id == owner_id)
    )
    profile = result.scalars().first()
    if profile is None or not profile.is_admin:
        raise api_error(403, "forbidden", "WCS admin access required")
    return owner_id
