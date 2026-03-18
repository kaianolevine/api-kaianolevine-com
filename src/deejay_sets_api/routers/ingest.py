from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_current_owner, get_settings
from ..database import get_db_session
from ..models import Set as DbSet
from ..models import Track as DbTrack
from ..schemas import Envelope, IngestResponseData, IngestSet, success_envelope
from ..services.reconciliation import reconcile_set_tracks

router = APIRouter()


@router.post(
    "/ingest",
    response_model=Envelope[IngestResponseData],
    summary="Ingest set + reconcile catalog",
    description="Accept a set with tracks, reconcile, and return catalog upsert stats.",
)
async def ingest_set(
    payload: IngestSet = Body(..., embed=False),
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[IngestResponseData]:
    settings = get_settings()

    db_set = DbSet(
        owner_id=owner_id,
        set_date=payload.set_date,
        venue=payload.venue,
        source_file=payload.source_file,
    )
    session.add(db_set)
    await session.flush()

    tracks = [
        DbTrack(
            owner_id=owner_id,
            set_id=db_set.id,
            catalog_id=None,
            play_order=track.play_order,
            play_time=track.play_time,
            title=track.title,
            artist=track.artist,
            genre=track.genre,
            bpm=track.bpm,
            release_year=track.release_year,
            length_secs=track.length_secs,
            data_quality=None,
        )
        for track in payload.tracks
    ]
    session.add_all(tracks)
    await session.flush()

    result = await reconcile_set_tracks(
        session=session,
        owner_id=owner_id,
        set_date=payload.set_date,
        tracks=tracks,
    )

    await session.commit()

    data = IngestResponseData(
        set_id=db_set.id,
        tracks_created=len(tracks),
        catalog_new=result.catalog_new,
        catalog_updated=result.catalog_updated,
        catalog_unchanged=result.catalog_unchanged,
    )
    return success_envelope(data, count=1, version=settings.API_VERSION)
