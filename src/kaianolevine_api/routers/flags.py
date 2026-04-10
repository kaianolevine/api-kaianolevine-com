from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_owner
from ..config import get_settings
from ..database import get_db_session
from ..models import FeatureFlag as DbFeatureFlag
from ..schemas import (
    Envelope,
    FeatureFlagItem,
    FeatureFlagPatch,
    api_error,
    success_envelope,
)

router = APIRouter()


@router.get(
    "/flags",
    response_model=Envelope[list[FeatureFlagItem]],
    summary="List feature flags",
    description="List all feature flags. Protected.",
)
async def list_flags(
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[FeatureFlagItem]]:
    del owner_id  # owner check is the protection layer for now
    settings = get_settings()
    total = (
        await session.execute(select(func.count()).select_from(DbFeatureFlag))
    ).scalar_one()

    rows = (
        (
            await session.execute(
                select(DbFeatureFlag).order_by(DbFeatureFlag.name.asc())
            )
        )
        .scalars()
        .all()
    )
    data = [
        FeatureFlagItem(
            id=row.id,
            owner_id=row.owner_id,
            name=row.name,
            enabled=row.enabled,
            description=row.description,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    return success_envelope(
        data, count=len(data), total=total, version=settings.API_VERSION
    )


@router.patch(
    "/flags/{name}",
    response_model=Envelope[FeatureFlagItem],
    summary="Update feature flag state",
    description='Enable/disable a flag. Protected. Request body: { "enabled": true }',
)
async def patch_flag(
    name: Annotated[str, Path(min_length=1)],
    payload: FeatureFlagPatch,
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[FeatureFlagItem]:
    settings = get_settings()

    row = (
        await session.execute(select(DbFeatureFlag).where(DbFeatureFlag.name == name))
    ).scalar_one_or_none()
    if row is None:
        raise api_error(404, "not_found", "Feature flag not found")

    row.enabled = payload.enabled
    row.owner_id = owner_id
    await session.flush()
    await session.commit()
    await session.refresh(row)

    data = FeatureFlagItem(
        id=row.id,
        owner_id=row.owner_id,
        name=row.name,
        enabled=row.enabled,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    return success_envelope(data, count=1, total=1, version=settings.API_VERSION)
