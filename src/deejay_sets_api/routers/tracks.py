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
from ..schemas import Envelope, TrackDetail, TrackListItem, success_envelope

router = APIRouter()


@router.get(
    "/tracks",
    response_model=Envelope[list[TrackListItem]],
    summary="List tracks",
    description="Query tracks by title/artist, genre, BPM range, year, and data quality.",
)
async def list_tracks(
    artist: Annotated[str | None, Query()] = None,
    title: Annotated[str | None, Query()] = None,
    genre: Annotated[str | None, Query()] = None,
    bpm_min: Annotated[float | None, Query()] = None,
    bpm_max: Annotated[float | None, Query()] = None,
    year: Annotated[int | None, Query()] = None,
    data_quality: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[TrackListItem]]:
    settings = get_settings()

    stmt = select(DbTrack, DbSet).join(DbSet, DbTrack.set_id == DbSet.id)

    if artist:
        stmt = stmt.where(func.lower(DbTrack.artist).like(f"%{artist.lower()}%"))
    if title:
        stmt = stmt.where(func.lower(DbTrack.title).like(f"%{title.lower()}%"))
    if genre:
        stmt = stmt.where(DbTrack.genre == genre)
    if bpm_min is not None:
        stmt = stmt.where(DbTrack.bpm >= bpm_min)
    if bpm_max is not None:
        stmt = stmt.where(DbTrack.bpm <= bpm_max)
    if year is not None:
        start = dt.date(year, 1, 1)
        end = dt.date(year, 12, 31)
        stmt = stmt.where(DbSet.set_date >= start, DbSet.set_date <= end)
    if data_quality:
        stmt = stmt.where(DbTrack.data_quality == data_quality)

    stmt = stmt.order_by(
        DbSet.set_date.desc(),
        DbTrack.play_order.asc().nulls_last(),
        DbTrack.play_time.asc().nulls_last(),
    )
    stmt = stmt.limit(limit).offset(offset)

    rows = (await session.execute(stmt)).all()

    data = [
        TrackListItem(
            id=track.id,
            set_id=set_row.id,
            set_date=set_row.set_date,
            venue=set_row.venue,
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
        for track, set_row in rows
    ]

    return success_envelope(data, count=len(data), version=settings.API_VERSION)


@router.get(
    "/tracks/{id}",
    response_model=Envelope[TrackDetail],
    summary="Get track with set context",
    description="Returns a single track play including its set context.",
)
async def get_track(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[TrackDetail]:
    settings = get_settings()

    stmt = select(DbTrack, DbSet).join(DbSet, DbTrack.set_id == DbSet.id).where(DbTrack.id == id)
    row = (await session.execute(stmt)).first()
    if row is None:
        from ..schemas import api_error

        raise api_error(404, "not_found", "Track not found")

    track, set_row = row
    data = TrackDetail(
        id=track.id,
        set_id=set_row.id,
        set_date=set_row.set_date,
        venue=set_row.venue,
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
    return success_envelope(data, count=1, version=settings.API_VERSION)
