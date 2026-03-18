from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db_session
from ..models import Set as DbSet
from ..models import Track as DbTrack
from ..schemas import Envelope, SetDetail, SetListItem, SetTrackListItem, success_envelope

router = APIRouter()


@router.get(
    "/sets",
    response_model=Envelope[list[SetListItem]],
    summary="List sets",
    description="List sets. Query by year, venue (partial), and date ranges.",
)
async def list_sets(
    year: Annotated[int | None, Query()] = None,
    venue: Annotated[str | None, Query()] = None,
    date_from: Annotated[dt.date | None, Query()] = None,
    date_to: Annotated[dt.date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[SetListItem]]:
    settings = get_settings()

    if year is not None:
        date_from = dt.date(year, 1, 1)
        date_to = dt.date(year, 12, 31)

    stmt = select(DbSet)
    if venue:
        stmt = stmt.where(func.lower(DbSet.venue).like(f"%{venue.lower()}%"))
    if date_from:
        stmt = stmt.where(DbSet.set_date >= date_from)
    if date_to:
        stmt = stmt.where(DbSet.set_date <= date_to)

    stmt = stmt.order_by(DbSet.set_date.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()

    data = [
        SetListItem(
            id=row.id,
            set_date=row.set_date,
            year=row.set_date.year,
            venue=row.venue,
            source_file=row.source_file,
        )
        for row in rows
    ]

    return success_envelope(data, count=len(data), version=settings.API_VERSION)


def _track_to_item(track: DbTrack, *, set_venue: str, set_date: dt.date) -> SetTrackListItem:
    return SetTrackListItem(
        id=track.id,
        set_id=track.set_id,
        set_date=set_date,
        venue=set_venue,
        play_order=track.play_order,
        play_time=track.play_time,
        title=track.title,
        artist=track.artist,
        genre=track.genre,
        bpm=track.bpm,
        release_year=track.release_year,
        length_secs=track.length_secs,
        data_quality=track.data_quality,
        catalog_id=track.catalog_id,
    )


@router.get(
    "/sets/{id}",
    response_model=Envelope[SetDetail],
    summary="Get set detail with tracks",
    description="Returns a single set and its complete ordered track list.",
)
async def get_set(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[SetDetail]:
    settings = get_settings()

    set_row = await session.get(DbSet, id)
    if set_row is None:
        from ..schemas import api_error

        raise api_error(404, "not_found", "Set not found")

    stmt = (
        select(DbTrack)
        .where(DbTrack.set_id == id)
        .order_by(DbTrack.play_order.asc().nulls_last(), DbTrack.play_time.asc().nulls_last())
    )
    tracks = (await session.execute(stmt)).scalars().all()

    data = SetDetail(
        id=set_row.id,
        set_date=set_row.set_date,
        year=set_row.set_date.year,
        venue=set_row.venue,
        source_file=set_row.source_file,
        tracks=[
            _track_to_item(t, set_venue=set_row.venue, set_date=set_row.set_date) for t in tracks
        ],
    )
    return success_envelope(data, count=1, version=settings.API_VERSION)


@router.get(
    "/sets/{id}/tracks",
    response_model=Envelope[list[SetTrackListItem]],
    summary="List set tracks",
    description="Returns the ordered track list for a given set.",
)
async def get_set_tracks(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[SetTrackListItem]]:
    settings = get_settings()
    set_row = await session.get(DbSet, id)
    if set_row is None:
        from ..schemas import api_error

        raise api_error(404, "not_found", "Set not found")

    stmt = (
        select(DbTrack)
        .where(DbTrack.set_id == id)
        .order_by(DbTrack.play_order.asc().nulls_last(), DbTrack.play_time.asc().nulls_last())
    )
    tracks = (await session.execute(stmt)).scalars().all()

    data = [_track_to_item(t, set_venue=set_row.venue, set_date=set_row.set_date) for t in tracks]
    return success_envelope(data, count=len(data), version=settings.API_VERSION)
