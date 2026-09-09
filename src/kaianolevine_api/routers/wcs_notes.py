"""WCS notes router — /v1/wcs/transcripts and /v1/wcs/notes endpoints.

Write endpoints (POST) are called by transcription-cog, which authenticates
with its own named machine key and holds the wcs-writer role; each route
names the scope it requires. Read endpoints (GET) are called by
wcs.kaianolevine.com on a Clerk session. PATCH is for user-facing
visibility toggling.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from identity.types import Principal
from mini_app_polis import logger as logger_mod
from mini_app_polis.logger import LOG_START, LOG_SUCCESS
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_scope
from ..config import get_settings
from ..database import get_db_session
from ..models import LegacyWcsNote as DbNote
from ..models import WcsNoteGrant
from ..models import WcsSource as DbSource
from ..models import WcsSourceExtraction as DbSourceExtraction
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
        "Called by transcription-cog to persist the raw transcript text. "
        "Returns the transcript ID used to associate structured notes."
    ),
)
async def create_transcript(
    payload: WcsTranscriptCreate,
    response: Response,
    owner_id_principal: Principal = Depends(require_scope("wcs.transcripts.write")),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsTranscriptItem]:
    """Persist a raw WCS transcript, with idempotent re-ingestion.

    If no transcript exists for (owner_id, drive_file_id), creates one
    and returns 201. If one exists, updates its raw_text, demotes any
    active extractions on its associated source(s), and returns 200.

    The re-ingestion signal is the file's presence in the cog's input
    Drive folder — the operator workflow moves processed files out of
    that folder, so a file reappearing there means "process this again."
    """
    owner_id = owner_id_principal.subject
    log.info(
        "%s storing transcript source_filename=%s", LOG_START, payload.source_filename
    )

    existing_q = select(DbTranscript).where(
        DbTranscript.owner_id == owner_id,
        DbTranscript.drive_file_id == payload.drive_file_id,
    )
    existing = (await session.execute(existing_q)).scalar_one_or_none()

    if existing is None:
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
        response.status_code = status.HTTP_201_CREATED
        log.info("%s transcript created id=%s", LOG_SUCCESS, row.id)
    else:
        existing.raw_text = payload.raw_text
        existing.source_type = payload.source_type
        existing.source_filename = payload.source_filename

        demote_q = (
            update(DbSourceExtraction)
            .where(
                DbSourceExtraction.source_id.in_(
                    select(DbSource.id).where(DbSource.transcript_id == existing.id)
                ),
                DbSourceExtraction.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await session.execute(demote_q)
        await session.commit()
        await session.refresh(existing)
        row = existing
        log.info(
            "%s transcript re-ingested id=%s — active extractions demoted",
            LOG_SUCCESS,
            row.id,
        )

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
        "Called by transcription-cog to persist structured notes produced by the LLM. "
        "Requires a valid transcript_id from POST /v1/wcs/transcripts."
    ),
)
async def create_note(
    payload: WcsNoteCreate,
    owner_id_principal: Principal = Depends(require_scope("wcs.notes.write")),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsNoteItem]:
    """Persist one structured WCS note linked to a transcript."""
    owner_id = owner_id_principal.subject
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

    # Parse session_date from ISO-8601 string if provided.
    #
    # A rejected date used to become None and the route still answered 200,
    # so a caller sending "2026-09-09T14:00:00Z" instead of "2026-09-09" had
    # every note in the batch stored with a NULL date — sorting to the bottom
    # of both listing queries and showing no date in citations — with nothing
    # anywhere saying why. The caller sent a value; if it cannot be used, the
    # caller is the one who can fix it.
    session_date: dt.date | None = None
    if payload.session_date:
        try:
            session_date = dt.date.fromisoformat(payload.session_date)
        except ValueError:
            raise api_error(
                422,
                "invalid_session_date",
                (
                    f"session_date must be an ISO-8601 date (YYYY-MM-DD); "
                    f"got {payload.session_date!r}"
                ),
            ) from None

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
        "List notes visible to the authenticated user: default-visible notes plus "
        "any notes explicitly granted. Admins wanting all notes regardless of "
        "visibility should use GET /v1/wcs/notes/all."
    ),
)
async def list_notes(
    session_type: Annotated[str | None, Query()] = None,
    visibility: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    owner_id_principal: Principal = Depends(require_scope("wcs.notes.read")),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[WcsNoteItem]]:
    """List notes visible to the authenticated user.

    Reads _legacy_wcs_notes; superseded by GET /v1/wcs/wiki/sources.
    """
    owner_id = owner_id_principal.subject
    settings = get_settings()

    # Standard user filtering — no admin bypass.
    # Admins wanting all notes should use GET /v1/wcs/notes/all.
    grant_exists = exists().where(
        WcsNoteGrant.user_id == owner_id,
        WcsNoteGrant.note_id == DbNote.id,
    )
    accessible = or_(
        DbNote.is_default_visible.is_(True),
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
    "/wcs/notes/all",
    response_model=Envelope[list[WcsNoteItem]],
    summary="List all WCS notes",
    description=(
        "Returns all notes regardless of visibility. Requires "
        "`wcs.corpus.read` — held by the `wcs-admin` role (human "
        "administrators) and the `corpus-reader` role (wiki-curator-cog). "
        "Deliberately NOT `wcs.notes.read`: every human holds that scope "
        "by default via `wcs-reader`, and this endpoint bypasses "
        "per-source visibility, so mapping it there would expose private "
        "sources to every signed-in user."
    ),
)
async def list_all_notes(
    session_type: Annotated[str | None, Query()] = None,
    visibility: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    owner_id_principal: Principal = Depends(require_scope("wcs.corpus.read")),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[WcsNoteItem]]:
    """List all WCS notes for admin- and pipeline-driven workflows.

    TODO(service-auth): currently requires only a valid authenticated
    identity, not WCS admin. Before opening this API to less-trusted
    callers, swap ``get_current_owner`` back to a stricter dependency
    that recognizes admins AND a service-account allowlist. The
    blocking issue is that pipeline cogs (wiki-curator-cog, etc.) use
    Clerk M2M tokens and aren't naturally "admins" in the user-profile
    sense; promoting machines to ``is_admin=true`` would also grant
    them user-management permissions they shouldn't have.

    Reads _legacy_wcs_notes; superseded by GET /v1/wcs/wiki/admin/sources.
    """
    _ = owner_id_principal.subject
    settings = get_settings()

    stmt = (
        select(DbNote)
        .order_by(DbNote.session_date.desc().nullslast(), DbNote.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if session_type:
        stmt = stmt.where(DbNote.session_type == session_type)
    if visibility:
        stmt = stmt.where(DbNote.visibility == visibility)

    total_stmt = select(func.count()).select_from(DbNote)
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
    owner_id_principal: Principal = Depends(require_scope("wcs.notes.read")),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsNoteItem]:
    """Return one note when the caller has visibility access.

    Reads _legacy_wcs_notes; superseded by GET /v1/wcs/wiki/sources/{id}.
    """
    owner_id = owner_id_principal.subject
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
    owner_id_principal: Principal = Depends(require_scope("wcs.notes.read")),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[WcsNoteItem]:
    """Update user-facing visibility for one owned note.

    Reads _legacy_wcs_notes; superseded by substrate wiki/admin endpoints.
    """
    owner_id = owner_id_principal.subject
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
