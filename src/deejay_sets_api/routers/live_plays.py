from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_owner
from ..config import get_settings
from ..database import get_db_session
from ..models import LivePlay as DbLivePlay
from ..schemas import (
    Envelope,
    LivePlayRecord,
    LivePlaysIngest,
    LivePlaysResponseData,
    success_envelope,
)
from ..services.flags import is_enabled

router = APIRouter()


@router.post(
    "/live-plays",
    response_model=Envelope[LivePlaysResponseData],
    summary="Ingest live play history",
    description="Ingest live play history into standalone live_plays table.",
)
async def ingest_live_plays(
    payload: LivePlaysIngest = Body(..., embed=False),
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[LivePlaysResponseData]:
    settings = get_settings()
    if not await is_enabled("flags.deejay_api.live_plays_enabled", session):
        raise HTTPException(
            status_code=503,
            detail={"code": "feature_disabled", "message": "Live plays are currently disabled"},
        )

    inserted = 0
    skipped = 0

    for play in payload.plays:
        stmt = pg_insert(DbLivePlay).values(
            owner_id=owner_id,
            played_at=play.played_at,
            title=play.title,
            artist=play.artist,
        ).on_conflict_do_nothing(
            constraint="uq_live_plays_owner_title_artist_played_at"
        )
        result = await session.execute(stmt)
        if result.rowcount == 1:
            inserted += 1
        else:
            skipped += 1

    await session.commit()
    data = LivePlaysResponseData(inserted=inserted, skipped=skipped)
    return success_envelope(data, count=1, version=settings.API_VERSION)


@router.get(
    "/live-plays/recent",
    response_model=Envelope[list[LivePlayRecord]],
    summary="Recent live plays",
    description="List recent plays from live history ordered by played_at descending.",
)
async def list_recent_live_plays(
    limit: int = Query(default=50, ge=1, le=200),
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[LivePlayRecord]]:
    settings = get_settings()
    if not await is_enabled("flags.deejay_api.live_plays_enabled", session):
        raise HTTPException(
            status_code=503,
            detail={"code": "feature_disabled", "message": "Live plays are currently disabled"},
        )

    stmt = (
        select(DbLivePlay)
        .where(DbLivePlay.owner_id == owner_id)
        .order_by(DbLivePlay.played_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()

    data = [
        LivePlayRecord(
            id=row.id,
            played_at=row.played_at,
            title=row.title,
            artist=row.artist,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return success_envelope(data, count=len(data), version=settings.API_VERSION)
