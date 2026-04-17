from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx
import jwt
from fastapi import Depends, Header
from jwt import PyJWK
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings
from .database import get_db_session
from .models import WcsUserProfile
from .schemas import api_error
from .services.flags import is_enabled

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Authentication — Project Keystone dual-auth bridge
#
# Flags (DB):
#   flags.keystone.legacy_auth_enabled  → accept X-Owner-Id (+ KAIANO_API_OWNER_ID)
#   flags.keystone.clerk_auth_enabled   → verify Authorization: Bearer <JWT> (RS256)
#
# Phase 1: legacy=TRUE,  clerk=FALSE  → X-Owner-Id only
# Phase 2: legacy=TRUE,  clerk=TRUE   → JWT first, then legacy
# Phase 3: legacy=FALSE, clerk=TRUE   → JWT only
# ---------------------------------------------------------------------------

# JWKS document cache: url -> (monotonic_expiry, jwks_json). TTL 5 minutes.
_jwks_doc_cache: dict[str, tuple[float, dict[str, Any]]] = {}


async def _fetch_jwks_document(jwks_url: str) -> dict[str, Any]:
    """Fetch JWKS JSON with httpx; reuse cached document for 5 minutes."""
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
    except Exception as exc:
        logger.error("[keystone] JWT decode failed: %s", exc)
        return None


async def verify_clerk_jwt(token: str, settings: Settings) -> str | None:
    """
    Verify a Clerk session JWT (RS256) or M2M opaque token.
    Returns the ``sub`` claim on success, or None on failure / misconfiguration.
    """
    if not settings.CLERK_JWKS_URL or not settings.CLERK_ISSUER:
        return None

    # Opaque tokens are not JWTs; verify them via Clerk's BAPI endpoint.
    if token.count(".") != 2:
        return await _verify_opaque_token(token, settings)

    try:
        jwks_doc = await _fetch_jwks_document(settings.CLERK_JWKS_URL)
    except Exception as exc:
        logger.error("[keystone] JWKS fetch failed: %s", exc)
        return None
    return await asyncio.to_thread(_decode_clerk_jwt_sync, token, settings, jwks_doc)


async def _verify_opaque_token(token: str, settings: Settings) -> str | None:
    """
    Verify a Clerk M2M opaque token via the BAPI verify endpoint.
    Returns ``sub`` (machine subject) on success, or None on failure.
    """
    secret_key = settings.CLERK_SECRET_KEY
    if not secret_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.clerk.com/v1/m2m_tokens/verify",
                headers={
                    "Authorization": f"Bearer {secret_key}",
                    "Content-Type": "application/json",
                },
                json={"token": token},
            )
        if not resp.is_success:
            return None
        data = resp.json()
        sub = data.get("subject") or data.get("sub")
        return str(sub) if sub else None
    except Exception as exc:
        logger.error("[keystone] Opaque token verify failed: %s", exc)
        return None


async def get_current_owner(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_owner_id: str | None = Header(default=None, alias="X-Owner-Id"),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_db_session),
) -> str:
    """
    Project Keystone dual-auth bridge.

    Resolves owner identity from Clerk JWT (``sub``) and/or legacy ``X-Owner-Id``,
    depending on ``flags.keystone.*`` feature flags in the database.
    """
    clerk_enabled = await is_enabled("flags.keystone.clerk_auth_enabled", session)
    legacy_enabled = await is_enabled("flags.keystone.legacy_auth_enabled", session)

    if clerk_enabled and authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            sub = await verify_clerk_jwt(token, settings)
            if sub:
                return sub
        if not legacy_enabled:
            raise api_error(401, "unauthorized", "Invalid or expired token")

    if legacy_enabled:
        owner = x_owner_id or settings.KAIANO_API_OWNER_ID
        if owner:
            return owner

    raise api_error(401, "unauthorized", "Authentication required")


async def require_wcs_admin(
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> str:
    """
    Ensures the caller (Clerk ``sub`` from JWT or X-Owner-Id) is a WCS admin.
    """
    result = await session.execute(
        select(WcsUserProfile).where(WcsUserProfile.user_id == owner_id)
    )
    profile = result.scalars().first()
    if profile is None or not profile.is_admin:
        raise api_error(403, "forbidden", "WCS admin access required")
    return owner_id
