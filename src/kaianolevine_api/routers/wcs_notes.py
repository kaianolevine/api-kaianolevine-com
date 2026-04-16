"""WCS notes router — /v1/wcs/transcripts and /v1/wcs/notes endpoints.

Write endpoints (POST) are called by notes-ingest-cog via X-Internal-API-Key.
Read endpoints (GET) are called by wcs.kaianolevine.com.
PATCH is for user-facing visibility toggling.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from mini_app_polis import logger as logger_mod
from mini_app_polis.logger import LOG_START, LOG_SUCCESS
from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_owner
from ..config import get_settings
from ..database import get_db_session
from ..models import WcsNote as DbNote
from ..models import WcsNoteGrant, WcsUserProfile
from ..models import WcsTranscript as DbTranscript
from ..schemas import (
    Envelope,
    WcsNoteCreate,
    WcsNoteItem,
    WcsNotePatch,
    WcsTranscriptCreate,
    WcsTranscriptItem,
    api_error,
    success_envelope,
)
from ..services.wcs_access import user_can_see_note

router = APIRouter()
log = logger_mod.get_logger()


# ── Transcripts ───────────────────────────────────────────────────────────────


@router.post(
    "/wcs/transcripts",
    response_model=Envelope[WcsTranscriptItem],
    summary="Store a raw WCS transcript",
    description=(
        "Called by notes-ingest-cog to persist the raw transcript text. "
        "Returns the transcript ID used to associate structured notes."
    ),
)
async def create_transcript(
    payload: WcsTranscriptCreate,
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsTranscriptItem]:
    log.info(
        "%s storing transcript source_filename=%s", LOG_START, payload.source_filename
    )

    row = DbTranscript(
        owner_id=owner_id,
        raw_text=payload.raw_text,
        source_type=payload.source_type,
        source_filename=payload.source_filename,
        drive_file_id=payload.drive_file_id,
    )
    session.add(row)
    await session.flush()
    await session.commit()
    await session.refresh(row)

    log.info("%s transcript stored id=%s", LOG_SUCCESS, row.id)

    settings = get_settings()
    data = WcsTranscriptItem(
        id=row.id,
        source_type=row.source_type,
        source_filename=row.source_filename,
        drive_file_id=row.drive_file_id,
        created_at=row.created_at,
    )
    return success_envelope(data, count=1, total=1, version=settings.API_VERSION)


# ── Notes — write ─────────────────────────────────────────────────────────────


@router.post(
    "/wcs/notes",
    response_model=Envelope[WcsNoteItem],
    summary="Store structured WCS notes",
    description=(
        "Called by notes-ingest-cog to persist structured notes produced by the LLM. "
        "Requires a valid transcript_id from POST /v1/wcs/transcripts."
    ),
)
async def create_note(
    payload: WcsNoteCreate,
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsNoteItem]:
    log.info(
        "%s storing note transcript_id=%s session_type=%s",
        LOG_START,
        payload.transcript_id,
        payload.session_type,
    )

    # Validate transcript exists and belongs to this owner
    transcript_id = uuid.UUID(payload.transcript_id)
    result = await session.execute(
        select(DbTranscript).where(
            DbTranscript.id == transcript_id,
            DbTranscript.owner_id == owner_id,
        )
    )
    transcript = result.scalars().first()
    if transcript is None:
        raise api_error(404, "transcript_not_found", "Transcript not found")

    # Parse session_date from ISO-8601 string if provided
    session_date: dt.date | None = None
    if payload.session_date:
        try:
            session_date = dt.date.fromisoformat(payload.session_date)
        except ValueError:
            session_date = None

    row = DbNote(
        owner_id=owner_id,
        transcript_id=transcript_id,
        title=payload.title,
        session_date=session_date,
        session_type=payload.session_type,
        instructors=payload.instructors,
        students=payload.students,
        organization=payload.organization,
        visibility=payload.visibility,
        model=payload.model,
        provider=payload.provider,
        notes_json=payload.notes_json,
    )
    session.add(row)
    await session.flush()
    await session.commit()
    await session.refresh(row)

    log.info("%s note stored id=%s", LOG_SUCCESS, row.id)

    settings = get_settings()
    data = _to_item(row)
    return success_envelope(data, count=1, total=1, version=settings.API_VERSION)


# ── Notes — read ──────────────────────────────────────────────────────────────


@router.get(
    "/wcs/notes",
    response_model=Envelope[list[WcsNoteItem]],
    summary="List WCS notes",
    description=(
        "List structured notes with optional filtering by session type and visibility. "
        "Private notes are only returned for the authenticated owner. "
        "Public notes are visible to all."
    ),
)
async def list_notes(
    session_type: Annotated[str | None, Query()] = None,
    visibility: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    as_user: Annotated[
        bool,
        Query(description="Skip admin override, apply standard user filtering."),
    ] = False,  # TODO: remove when X-Owner-Id auth is replaced with Clerk JWT auth
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[WcsNoteItem]]:
    settings = get_settings()

    grant_exists = exists().where(
        WcsNoteGrant.user_id == owner_id,
        WcsNoteGrant.note_id == DbNote.id,
    )

    if as_user:
        # Standard user filtering — ignore admin status
        accessible = or_(
            DbNote.is_default_visible.is_(True),
            grant_exists,
        )
    else:
        admin_exists = exists().where(
            WcsUserProfile.user_id == owner_id,
            WcsUserProfile.is_admin.is_(True),
        )
        accessible = or_(
            DbNote.is_default_visible.is_(True),
            admin_exists,
            grant_exists,
        )

    stmt = (
        select(DbNote)
        .where(accessible)
        .order_by(DbNote.session_date.desc().nullslast(), DbNote.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if session_type:
        stmt = stmt.where(DbNote.session_type == session_type)
    if visibility:
        stmt = stmt.where(DbNote.visibility == visibility)

    total_stmt = select(func.count()).select_from(DbNote).where(accessible)
    if session_type:
        total_stmt = total_stmt.where(DbNote.session_type == session_type)
    if visibility:
        total_stmt = total_stmt.where(DbNote.visibility == visibility)
    total = (await session.execute(total_stmt)).scalar_one()

    rows = (await session.execute(stmt)).scalars().all()
    data = [_to_item(r) for r in rows]
    return success_envelope(
        data, count=len(data), total=total or 0, version=settings.API_VERSION
    )


@router.get(
    "/wcs/notes/{note_id}",
    response_model=Envelope[WcsNoteItem],
    summary="Get a single WCS note",
    description="Returns a single note by ID. Private notes require owner auth.",
)
async def get_note(
    note_id: uuid.UUID,
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsNoteItem]:
    settings = get_settings()

    result = await session.execute(select(DbNote).where(DbNote.id == note_id))
    row = result.scalars().first()

    if row is None:
        raise api_error(404, "note_not_found", "Note not found")

    if not await user_can_see_note(session, owner_id, row):
        raise api_error(403, "forbidden", "Note not visible for this user")

    return success_envelope(
        _to_item(row), count=1, total=1, version=settings.API_VERSION
    )


# ── Notes — patch ─────────────────────────────────────────────────────────────


@router.patch(
    "/wcs/notes/{note_id}",
    response_model=Envelope[WcsNoteItem],
    summary="Update note visibility",
    description="Toggle a note between private and public. Owner only.",
)
async def patch_note(
    note_id: uuid.UUID,
    payload: WcsNotePatch,
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsNoteItem]:
    settings = get_settings()

    result = await session.execute(
        select(DbNote).where(DbNote.id == note_id, DbNote.owner_id == owner_id)
    )
    row = result.scalars().first()

    if row is None:
        raise api_error(404, "note_not_found", "Note not found")

    row.visibility = payload.visibility
    await session.commit()
    await session.refresh(row)

    return success_envelope(
        _to_item(row), count=1, total=1, version=settings.API_VERSION
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _to_item(row: DbNote) -> WcsNoteItem:
    return WcsNoteItem(
        id=row.id,
        transcript_id=row.transcript_id,
        title=row.title,
        session_date=row.session_date,
        session_type=row.session_type,
        instructors=row.instructors or [],
        students=row.students or [],
        organization=row.organization or "",
        is_default_visible=row.is_default_visible,
        visibility=row.visibility,
        model=row.model,
        provider=row.provider,
        notes_json=row.notes_json,
        created_at=row.created_at,
    )
