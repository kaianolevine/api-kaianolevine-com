from __future__ import annotations

import uuid
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db_session
from ..models import Set as DbSet
from ..models import Track as DbTrack
from ..models import TrackCatalog as DbCatalog
from ..schemas import (
    Envelope,
    StatsByYearItem,
    StatsOverview,
    StatsTopArtistItem,
    StatsTopTrackItem,
    success_envelope,
)

router = APIRouter()


@router.get(
    "/stats/overview",
    response_model=Envelope[StatsOverview],
    summary="Stats overview",
    description="Return totals, unique tracks, years active, and most played artist.",
)
async def stats_overview(
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[StatsOverview]:
    settings = get_settings()

    total_sets = (await session.execute(select(func.count()).select_from(DbSet))).scalar_one()
    total_plays = (await session.execute(select(func.count()).select_from(DbTrack))).scalar_one()

    unique_tracks = (
        await session.execute(
            select(func.count(func.distinct(DbTrack.catalog_id))).where(
                DbTrack.catalog_id.is_not(None)
            )
        )
    ).scalar_one()

    sets = (await session.execute(select(DbSet.set_date))).scalars().all()
    years_active = len({d.year for d in sets})

    most_played = (
        await session.execute(
            select(DbTrack.artist, func.count(DbTrack.id))
            .group_by(DbTrack.artist)
            .order_by(func.count(DbTrack.id).desc())
            .limit(1)
        )
    ).first()
    most_played_artist = most_played[0] if most_played else None

    data = StatsOverview(
        total_sets=total_sets,
        total_plays=total_plays,
        unique_tracks=unique_tracks,
        years_active=years_active,
        most_played_artist=most_played_artist,
    )
    return success_envelope(data, count=1, version=settings.API_VERSION)


@router.get(
    "/stats/by-year",
    response_model=Envelope[list[StatsByYearItem]],
    summary="Stats by year",
    description="Return set count and track count grouped by year.",
)
async def stats_by_year(
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[StatsByYearItem]]:
    settings = get_settings()

    sets = (await session.execute(select(DbSet.id, DbSet.set_date))).all()
    year_to_set_ids: dict[int, list[uuid.UUID]] = defaultdict(list)
    for set_id, set_date in sets:
        year_to_set_ids[set_date.year].append(set_id)

    tracks = (
        await session.execute(
            select(DbTrack.id, DbTrack.set_id).join(DbSet, DbTrack.set_id == DbSet.id)
        )
    ).all()
    year_to_track_count: Counter[int] = Counter()
    # Use sets query for year mapping
    set_id_to_year: dict[uuid.UUID, int] = {}
    for set_id, set_date in sets:
        set_id_to_year[set_id] = set_date.year
    for track_id, set_id in tracks:
        year_to_track_count[set_id_to_year.get(set_id)] += 1  # type: ignore[arg-type]

    years = sorted(year_to_set_ids.keys())
    data = [
        StatsByYearItem(
            year=y,
            set_count=len(year_to_set_ids[y]),
            track_count=year_to_track_count[y],
        )
        for y in years
    ]

    return success_envelope(data, count=len(data), version=settings.API_VERSION)


@router.get(
    "/stats/top-artists",
    response_model=Envelope[list[StatsTopArtistItem]],
    summary="Top artists",
    description="Most played artists ranked by play count.",
)
async def stats_top_artists(
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[StatsTopArtistItem]]:
    settings = get_settings()

    rows = (
        await session.execute(
            select(DbTrack.artist, func.count(DbTrack.id))
            .group_by(DbTrack.artist)
            .order_by(func.count(DbTrack.id).desc())
            .limit(10)
        )
    ).all()

    data = [StatsTopArtistItem(artist=artist, play_count=count) for artist, count in rows]
    return success_envelope(data, count=len(data), version=settings.API_VERSION)


@router.get(
    "/stats/top-tracks",
    response_model=Envelope[list[StatsTopTrackItem]],
    summary="Top tracks",
    description="Most played tracks ranked by catalog play count.",
)
async def stats_top_tracks(
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[StatsTopTrackItem]]:
    settings = get_settings()

    rows = (
        (await session.execute(select(DbCatalog).order_by(DbCatalog.play_count.desc()).limit(10)))
        .scalars()
        .all()
    )

    data = [
        StatsTopTrackItem(
            catalog_id=row.id, title=row.title, artist=row.artist, play_count=row.play_count
        )
        for row in rows
    ]
    return success_envelope(data, count=len(data), version=settings.API_VERSION)
