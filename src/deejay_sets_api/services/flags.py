from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import FeatureFlag


async def is_enabled(name: str, session: AsyncSession) -> bool:
    """
    Check if a feature flag is enabled.
    Returns True if the flag exists and is enabled.
    Returns True if the flag does not exist (default open).
    """
    result = await session.execute(select(FeatureFlag).where(FeatureFlag.name == name))
    flag = result.scalar_one_or_none()
    if flag is None:
        return True
    return flag.enabled

