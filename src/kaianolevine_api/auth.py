from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings
from .database import get_db_session
from .models import WcsUserProfile
from .schemas import api_error

# ---------------------------------------------------------------------------
# Authentication
#
# CURRENT: Simple header-based auth using X-Owner-Id or KAIANO_API_OWNER_ID fallback.
# No real security — intended for internal processor-to-API calls only.
#
# FUTURE (when deejaytools.com or another frontend has real user accounts):
# Replace with Clerk JWT verification. The scaffolding for this is already
# planned:
#
#   1. Set CLERK_AUTH_ENABLED=true in Railway
#   2. Set CLERK_JWKS_URL to your Clerk app's JWKS endpoint
#   3. Replace get_current_owner below with JWKS-based JWT verification
#      using PyJWT[crypto] — verify RS256 tokens, extract `sub` as owner
#   4. Update KaianoApiClient in kaiano-common-utils to use Clerk M2M tokens
#      instead of X-Owner-Id (use a JWT Template in the Clerk dashboard +
#      Clerk Backend SDK to issue short-lived tokens, cached until expiry)
#
# See: https://clerk.com/docs/backend-requests/making/jwt-templates
#
# PROJECT KEYSTONE — transition sequence:
#
#   Phase 1 (now):     legacy=TRUE,  clerk=FALSE  → X-Owner-Id only (current)
#   Phase 2 (cutover): legacy=TRUE,  clerk=TRUE   → both accepted; migrate cogs
#   Phase 3 (cleanup): legacy=FALSE, clerk=TRUE   → Clerk JWT only
#
# Flags:
#   flags.keystone.legacy_auth_enabled  — checked before falling back to X-Owner-Id
#   flags.keystone.clerk_auth_enabled   — checked before attempting JWT verification
#
# The auth.py implementation will read these flags from the DB via is_enabled()
# once the Clerk upgrade begins. No code changes are needed until Phase 2.
# ---------------------------------------------------------------------------


def get_current_owner(
    x_owner_id: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Returns the owner identity for the current request.

    Reads from X-Owner-Id request header, falls back to KAIANO_API_OWNER_ID
    from settings if header is not present.

    TODO: Replace with Clerk JWT verification before exposing this API
    to real user traffic. See module docstring above for the upgrade path.
    """
    return x_owner_id or settings.KAIANO_API_OWNER_ID


async def require_wcs_admin(
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> str:
    """
    Ensures the caller (Clerk sub in X-Owner-Id) is a WCS admin.
    The WCS site SSR passes the Clerk `sub` as X-Owner-Id on admin API calls.
    """
    result = await session.execute(
        select(WcsUserProfile).where(WcsUserProfile.user_id == owner_id)
    )
    profile = result.scalars().first()
    if profile is None or not profile.is_admin:
        raise api_error(403, "forbidden", "WCS admin access required")
    return owner_id
