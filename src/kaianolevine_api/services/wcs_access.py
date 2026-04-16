"""WCS note visibility rules (default-visible catalog, grants, admins)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import WcsNote as DbNote
from ..models import WcsNoteGrant, WcsUserProfile


async def user_can_see_note(
    session: AsyncSession,
    user_id: str,
    note: DbNote,
) -> bool:
    """
    Returns True if the user is allowed to see this note.

    Rules (in order):
      1. Note is default-visible → any signed-in user can see it
      2. User is a WCS admin → can see everything
      3. User has an explicit grant for this note → can see it
      4. Otherwise → False
    """
    if note.is_default_visible:
        return True

    result = await session.execute(
        select(WcsUserProfile).where(WcsUserProfile.user_id == user_id)
    )
    profile = result.scalars().first()
    if profile is None:
        return False
    if profile.is_admin:
        return True

    grant = await session.execute(
        select(WcsNoteGrant).where(
            WcsNoteGrant.user_id == user_id,
            WcsNoteGrant.note_id == note.id,
        )
    )
    return grant.scalars().first() is not None
