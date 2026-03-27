from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_owner
from ..config import get_settings
from ..database import get_db_session
from ..models import Set as DbSet
from ..schemas import Envelope, IngestResponseData, IngestSet, success_envelope
from ..services.flags import is_enabled
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
    if not await is_enabled("flags.deejay_api.ingest_enabled", session):
        raise HTTPException(
            status_code=503,
            detail={"code": "feature_disabled", "message": "Ingest is currently disabled"},
        )

    existing_set = None
    if payload.source_file:
        lookup = await session.execute(
            select(DbSet).where(
                DbSet.owner_id == owner_id,
                DbSet.source_file == payload.source_file,
            )
        )
        existing_set = lookup.scalars().first()

    if existing_set is not None:
        db_set = existing_set
        is_reingestion = True
    else:
        db_set = DbSet(
            owner_id=owner_id,
            set_date=payload.set_date,
            venue=payload.venue,
            source_file=payload.source_file,
        )
        session.add(db_set)
        await session.flush()
        is_reingestion = False

    result = await reconcile_set_tracks(
        session=session,
        owner_id=owner_id,
        set_id=db_set.id,
        set_date=payload.set_date,
        tracks=payload.tracks,
        is_reingestion=is_reingestion,
    )

    await session.commit()

    data = IngestResponseData(
        set_id=db_set.id,
        tracks_created=result.tracks_inserted,
        catalog_new=result.catalog_new,
        catalog_updated=result.catalog_updated,
        catalog_unchanged=result.catalog_unchanged,
    )
    return success_envelope(data, count=1, version=settings.API_VERSION)
