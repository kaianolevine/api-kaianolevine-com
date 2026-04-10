from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_owner
from ..config import get_settings
from ..database import get_db_session
from ..models import SpotifyPlaylist as DbSpotifyPlaylist
from ..schemas import (
    Envelope,
    SpotifyPlaylistItem,
    SpotifyPlaylistsIngest,
    SpotifyPlaylistsIngestResponse,
    success_envelope,
)

router = APIRouter()


@router.get(
    "/spotify/playlists",
    response_model=Envelope[list[SpotifyPlaylistItem]],
    summary="List Spotify playlists",
    description="Public snapshot of playlists pushed by the cog, ordered by name.",
)
async def list_spotify_playlists(
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[SpotifyPlaylistItem]]:
    settings = get_settings()
    total = (
        await session.execute(select(func.count()).select_from(DbSpotifyPlaylist))
    ).scalar_one()
    stmt = select(DbSpotifyPlaylist).order_by(DbSpotifyPlaylist.name.asc())
    rows = (await session.execute(stmt)).scalars().all()

    data = [
        SpotifyPlaylistItem(
            id=row.id,
            name=row.name,
            url=row.url,
            uri=row.uri,
            type=row.playlist_type,
            public=row.public,
            collaborative=row.collaborative,
            snapshot_id=row.snapshot_id,
            tracks_total=row.tracks_total,
            owner_id=row.owner_id,
            owner_name=row.owner_name,
            captured_at=row.captured_at,
        )
        for row in rows
    ]
    return success_envelope(
        data, count=len(data), total=total, version=settings.API_VERSION
    )


@router.post(
    "/spotify/playlists",
    response_model=Envelope[SpotifyPlaylistsIngestResponse],
    summary="Ingest Spotify playlist snapshot",
    description="Upsert playlists; rows are updated only when snapshot_id changes.",
)
async def ingest_spotify_playlists(
    payload: SpotifyPlaylistsIngest = Body(..., embed=False),
    _owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[SpotifyPlaylistsIngestResponse]:
    settings = get_settings()
    tbl = DbSpotifyPlaylist.__table__

    upserted = 0
    unchanged = 0

    for pl in payload.playlists:
        insert_stmt = pg_insert(tbl).values(
            id=pl.id,
            name=pl.name,
            url=pl.url,
            uri=pl.uri,
            public=pl.public,
            collaborative=pl.collaborative,
            snapshot_id=pl.snapshot_id,
            tracks_total=pl.tracks_total,
            owner_id=pl.owner_id,
            owner_name=pl.owner_name,
            **{"type": pl.type},
        )
        excluded = insert_stmt.excluded
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[tbl.c.id],
            set_={
                "name": excluded.name,
                "url": excluded.url,
                "uri": excluded.uri,
                "public": excluded.public,
                "collaborative": excluded.collaborative,
                "snapshot_id": excluded.snapshot_id,
                "tracks_total": excluded.tracks_total,
                "owner_id": excluded.owner_id,
                "owner_name": excluded.owner_name,
                "captured_at": func.now(),
                **{"type": excluded.type},
            },
            where=tbl.c.snapshot_id.is_distinct_from(excluded.snapshot_id),
        )
        result = await session.execute(stmt)
        if result.rowcount == 1:
            upserted += 1
        else:
            unchanged += 1

    await session.commit()
    data = SpotifyPlaylistsIngestResponse(upserted=upserted, unchanged=unchanged)
    return success_envelope(data, count=1, total=1, version=settings.API_VERSION)
