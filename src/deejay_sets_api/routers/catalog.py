from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_owner
from ..config import get_settings
from ..database import get_db_session
from ..models import Set as DbSet
from ..models import Track as DbTrack
from ..models import TrackCatalog as DbCatalog
from ..schemas import (
    CatalogDetail,
    CatalogListItem,
    CatalogPatch,
    CatalogPlayHistoryItem,
    Envelope,
    api_error,
    success_envelope,
)

router = APIRouter()


@router.get(
    "/catalog",
    response_model=Envelope[list[CatalogListItem]],
    summary="List catalog entries",
    description="List track_catalog entries with optional filters.",
)
async def list_catalog(
    artist: Annotated[str | None, Query()] = None,
    title: Annotated[str | None, Query()] = None,
    confidence: Annotated[str | None, Query()] = None,
    min_play_count: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[CatalogListItem]]:
    settings = get_settings()

    stmt = select(DbCatalog).order_by(
        DbCatalog.play_count.desc(), DbCatalog.last_played.desc().nullslast()
    )

    if artist:
        stmt = stmt.where(func.lower(DbCatalog.artist).like(f"%{artist.lower()}%"))
    if title:
        stmt = stmt.where(func.lower(DbCatalog.title).like(f"%{title.lower()}%"))
    if confidence:
        stmt = stmt.where(DbCatalog.confidence == confidence)
    if min_play_count is not None:
        stmt = stmt.where(DbCatalog.play_count >= min_play_count)

    stmt = stmt.limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()

    data = [
        CatalogListItem(
            id=row.id,
            title=row.title,
            artist=row.artist,
            confidence=row.confidence,
            source=row.source,
            genre=row.genre,
            bpm=row.bpm,
            release_year=row.release_year,
            play_count=row.play_count,
            first_played=row.first_played,
            last_played=row.last_played,
        )
        for row in rows
    ]

    return success_envelope(data, count=len(data), version=settings.API_VERSION)


@router.get(
    "/catalog/{id}",
    response_model=Envelope[CatalogDetail],
    summary="Get catalog entry with play history",
    description="Returns a catalog entry and its play history across sets.",
)
async def get_catalog(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[CatalogDetail]:
    settings = get_settings()

    catalog = await session.get(DbCatalog, id)
    if catalog is None:
        raise api_error(404, "not_found", "Catalog entry not found")

    stmt = (
        select(DbTrack, DbSet)
        .join(DbSet, DbTrack.set_id == DbSet.id)
        .where(DbTrack.catalog_id == id)
        .order_by(
            DbSet.set_date.asc(),
            DbTrack.play_order.asc().nulls_last(),
            DbTrack.play_time.asc().nulls_last(),
        )
    )
    rows = (await session.execute(stmt)).all()

    play_history = [
        CatalogPlayHistoryItem(
            id=track.id,
            set_id=set_row.id,
            set_date=set_row.set_date,
            venue=set_row.venue,
            play_order=track.play_order,
            play_time=track.play_time,
            data_quality=track.data_quality,
        )
        for track, set_row in rows
    ]

    data = CatalogDetail(
        id=catalog.id,
        title=catalog.title,
        artist=catalog.artist,
        confidence=catalog.confidence,
        source=catalog.source,
        genre=catalog.genre,
        bpm=catalog.bpm,
        release_year=catalog.release_year,
        play_count=catalog.play_count,
        first_played=catalog.first_played,
        last_played=catalog.last_played,
        play_history=play_history,
    )

    return success_envelope(data, count=1, version=settings.API_VERSION)


@router.patch(
    "/catalog/{id}",
    response_model=Envelope[CatalogDetail],
    summary="Patch catalog metadata",
    description="Update catalog genre, bpm, and release year. Sets source to manual. Protected.",
)
async def patch_catalog(
    id: uuid.UUID,
    patch: CatalogPatch,
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[CatalogDetail]:
    catalog_stmt = select(DbCatalog).where(DbCatalog.id == id, DbCatalog.owner_id == owner_id)
    catalog = (await session.execute(catalog_stmt)).scalar_one_or_none()
    if catalog is None:
        raise api_error(404, "not_found", "Catalog entry not found")

    if patch.genre is not None:
        catalog.genre = patch.genre
    if patch.bpm is not None:
        catalog.bpm = patch.bpm
    if patch.release_year is not None:
        catalog.release_year = patch.release_year

    catalog.source = "manual"
    # SQLite doesn't reliably support server-side updated_at in tests; keeping it simple.

    await session.flush()
    await session.commit()

    # Re-use detail formatter by reloading via the getter logic.
    return await get_catalog(id=id, session=session)
