from __future__ import annotations

import time
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from jwt.algorithms import RSAAlgorithm

from .config import Settings, get_settings

_JWKS_CACHE_KEY: Any | None = None
_JWKS_CACHE_EXPIRES_AT: float = 0.0
_JWKS_CACHE_TTL_SECONDS = 60 * 60


async def get_jwks_key(jwks_url: str) -> Any:
    global _JWKS_CACHE_KEY, _JWKS_CACHE_EXPIRES_AT

    now = time.time()
    if _JWKS_CACHE_KEY is not None and now < _JWKS_CACHE_EXPIRES_AT:
        return _JWKS_CACHE_KEY

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    keys = payload.get("keys")
    if not isinstance(keys, list) or not keys:
        raise HTTPException(status_code=401, detail="Invalid token")

    first_key = keys[0]
    if not isinstance(first_key, dict):
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        public_key = RSAAlgorithm.from_jwk(first_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    _JWKS_CACHE_KEY = public_key
    _JWKS_CACHE_EXPIRES_AT = now + _JWKS_CACHE_TTL_SECONDS
    return public_key


async def verify_clerk_token(token: str, jwks_url: str) -> str:
    try:
        key = await get_jwks_key(jwks_url)
        payload = jwt.decode(token, key=key, algorithms=["RS256"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise HTTPException(status_code=401, detail="Invalid token")
    return sub


async def get_current_owner(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> str:
    if not settings.CLERK_AUTH_ENABLED:
        return settings.OWNER_ID

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    if not settings.CLERK_JWKS_URL:
        raise HTTPException(status_code=401, detail="Invalid token")

    return await verify_clerk_token(token.strip(), settings.CLERK_JWKS_URL)
