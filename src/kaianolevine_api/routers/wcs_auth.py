"""WCS access control — profiles, admin users, note grants, default visibility."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from mini_app_polis import logger as logger_mod
from mini_app_polis.logger import LOG_START, LOG_SUCCESS
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_owner, require_wcs_admin
from ..config import get_settings
from ..database import get_db_session
from ..models import WcsNote as DbNote
from ..models import WcsNoteGrant, WcsUserProfile
from ..schemas import (
    Envelope,
    WcsMeUpsert,
    WcsNoteDefaultVisiblePatch,
    WcsNoteGrantCreate,
    WcsNoteGrantOut,
    WcsNoteItem,
    WcsUserProfileOut,
    WcsUserProfilePatch,
    api_error,
    success_envelope,
)
from .wcs_notes import _to_item

router = APIRouter()
log = logger_mod.get_logger()


# ── /wcs/me ───────────────────────────────────────────────────────────────────


@router.post(
    "/wcs/me",
    response_model=Envelope[WcsUserProfileOut],
    summary="Upsert WCS user profile",
    description=(
        "Upsert a WCS user profile for the authenticated Clerk user (X-Owner-Id). "
        "Creates the row if missing; updates email, display_name, and last_seen_at."
    ),
)
async def upsert_wcs_me(
    body: WcsMeUpsert,
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsUserProfileOut]:
    log.info("%s upsert WCS profile user_id=%s", LOG_START, owner_id)
    result = await session.execute(
        select(WcsUserProfile).where(WcsUserProfile.user_id == owner_id)
    )
    profile = result.scalars().first()
    now = dt.datetime.now(dt.UTC)

    if profile is None:
        profile = WcsUserProfile(
            user_id=owner_id,
            email=body.email,
            display_name=body.display_name,
            last_seen_at=now,
        )
        session.add(profile)
    else:
        profile.email = body.email or profile.email
        profile.display_name = body.display_name or profile.display_name
        profile.last_seen_at = now

    await session.commit()
    await session.refresh(profile)
    log.info("%s WCS profile upserted user_id=%s", LOG_SUCCESS, owner_id)

    settings = get_settings()
    data = WcsUserProfileOut.model_validate(profile)
    return success_envelope(data, count=1, total=1, version=settings.API_VERSION)


@router.get(
    "/wcs/me",
    response_model=Envelope[WcsUserProfileOut],
    summary="Get WCS user profile",
    description="Returns the WCS profile for the authenticated Clerk user.",
)
async def get_wcs_me(
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsUserProfileOut]:
    result = await session.execute(
        select(WcsUserProfile).where(WcsUserProfile.user_id == owner_id)
    )
    profile = result.scalars().first()
    if profile is None:
        raise api_error(404, "profile_not_found", "Profile not found")

    settings = get_settings()
    return success_envelope(
        WcsUserProfileOut.model_validate(profile),
        count=1,
        total=1,
        version=settings.API_VERSION,
    )


# ── /wcs/admin/users ──────────────────────────────────────────────────────────


@router.get(
    "/wcs/admin/users",
    response_model=Envelope[list[WcsUserProfileOut]],
    summary="List WCS users",
    description="Admin-only. Lists all WCS user profiles by last_seen_at descending.",
)
async def list_wcs_users(
    _admin_id: str = Depends(require_wcs_admin),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[WcsUserProfileOut]]:
    settings = get_settings()
    result = await session.execute(
        select(WcsUserProfile).order_by(WcsUserProfile.last_seen_at.desc())
    )
    rows = result.scalars().all()
    data = [WcsUserProfileOut.model_validate(p) for p in rows]
    return success_envelope(
        data, count=len(data), total=len(data), version=settings.API_VERSION
    )


@router.patch(
    "/wcs/admin/users/{user_id}",
    response_model=Envelope[WcsUserProfileOut],
    summary="Patch WCS user",
    description="Admin-only. Update fields such as is_admin.",
)
async def patch_wcs_user(
    user_id: str,
    body: WcsUserProfilePatch,
    _admin_id: str = Depends(require_wcs_admin),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsUserProfileOut]:
    settings = get_settings()
    result = await session.execute(
        select(WcsUserProfile).where(WcsUserProfile.user_id == user_id)
    )
    profile = result.scalars().first()
    if profile is None:
        raise api_error(404, "user_not_found", "User not found")

    if body.is_admin is not None:
        profile.is_admin = body.is_admin

    await session.commit()
    await session.refresh(profile)
    return success_envelope(
        WcsUserProfileOut.model_validate(profile),
        count=1,
        total=1,
        version=settings.API_VERSION,
    )


# ── /wcs/admin/grants ─────────────────────────────────────────────────────────


@router.get(
    "/wcs/admin/grants",
    response_model=Envelope[list[WcsNoteGrantOut]],
    summary="List WCS note grants",
    description="Admin-only. Optional filters by user_id and/or note_id.",
)
async def list_wcs_grants(
    user_id: Annotated[str | None, Query()] = None,
    note_id: Annotated[uuid.UUID | None, Query()] = None,
    _admin_id: str = Depends(require_wcs_admin),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[WcsNoteGrantOut]]:
    settings = get_settings()
    stmt = select(WcsNoteGrant).order_by(WcsNoteGrant.granted_at.desc())
    if user_id:
        stmt = stmt.where(WcsNoteGrant.user_id == user_id)
    if note_id:
        stmt = stmt.where(WcsNoteGrant.note_id == note_id)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    data = [WcsNoteGrantOut.model_validate(g) for g in rows]
    return success_envelope(
        data, count=len(data), total=len(data), version=settings.API_VERSION
    )


@router.post(
    "/wcs/admin/grants",
    response_model=Envelope[WcsNoteGrantOut],
    status_code=status.HTTP_201_CREATED,
    summary="Create WCS note grant",
    description="Admin-only. Grants a user access to a specific note.",
)
async def create_wcs_grant(
    body: WcsNoteGrantCreate,
    admin_id: str = Depends(require_wcs_admin),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsNoteGrantOut]:
    settings = get_settings()
    grant = WcsNoteGrant(
        user_id=body.user_id,
        note_id=body.note_id,
        granted_by=admin_id,
    )
    session.add(grant)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise api_error(409, "conflict", "Grant already exists") from None

    await session.refresh(grant)
    return success_envelope(
        WcsNoteGrantOut.model_validate(grant),
        count=1,
        total=1,
        version=settings.API_VERSION,
    )


@router.delete(
    "/wcs/admin/grants/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete WCS note grant",
    description="Admin-only.",
)
async def delete_wcs_grant(
    grant_id: uuid.UUID,
    _admin_id: str = Depends(require_wcs_admin),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    result = await session.execute(
        select(WcsNoteGrant).where(WcsNoteGrant.id == grant_id)
    )
    grant = result.scalars().first()
    if grant is None:
        raise api_error(404, "grant_not_found", "Grant not found")

    await session.delete(grant)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── /wcs/admin/notes/{note_id}/visibility ─────────────────────────────────────


@router.patch(
    "/wcs/admin/notes/{note_id}/visibility",
    response_model=Envelope[WcsNoteItem],
    summary="Set default note visibility",
    description="Admin-only. Controls catalog default visibility (is_default_visible).",
)
async def patch_wcs_note_default_visibility(
    note_id: uuid.UUID,
    body: WcsNoteDefaultVisiblePatch,
    _admin_id: str = Depends(require_wcs_admin),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsNoteItem]:
    settings = get_settings()
    result = await session.execute(select(DbNote).where(DbNote.id == note_id))
    note = result.scalars().first()
    if note is None:
        raise api_error(404, "note_not_found", "Note not found")

    note.is_default_visible = body.is_default_visible
    await session.commit()
    await session.refresh(note)

    return success_envelope(
        _to_item(note),
        count=1,
        total=1,
        version=settings.API_VERSION,
    )
