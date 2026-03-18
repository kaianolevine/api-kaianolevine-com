from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable
from datetime import date as dt_date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Track, TrackCatalog
from .normalization import normalize_for_matching


@dataclasses.dataclass(frozen=True)
class ReconciliationResult:
    catalog_new: int
    catalog_updated: int
    catalog_unchanged: int


def _data_quality_for_track(track: Track) -> str:
    # Core fields used to assess completeness for later matching/enrichment.
    core = [
        track.title,
        track.artist,
        track.genre,
        track.bpm,
        track.release_year,
        track.length_secs,
        track.play_time,
        track.play_order,
    ]
    populated = sum(1 for v in core if v is not None)

    if populated == 2:
        return "minimal"
    if populated == 8:
        return "complete"
    # The design doc uses 3-6 populated fields => partial; other cases are also partial.
    if 3 <= populated <= 6:
        return "partial"
    return "partial"


def _escalate_confidence(
    current: str,
    new_play_count: int,
    *,
    catalog_bpm: float | None,
    track_bpm: float | None,
    track_genre: str | None,
) -> str:
    current_lower = current.lower()
    if current_lower == "low":
        if new_play_count >= 2 or (track_bpm is not None and track_genre is not None):
            return "medium"
        return "low"

    if current_lower == "medium":
        if new_play_count >= 3 and catalog_bpm is not None and track_bpm is not None:
            if math.isfinite(catalog_bpm) and math.isfinite(track_bpm):
                if abs(catalog_bpm - track_bpm) <= 2:
                    return "high"
        return "medium"

    # Already high or unknown.
    return current_lower


async def reconcile_set_tracks(
    *,
    session: AsyncSession,
    owner_id: str,
    set_date: dt_date,
    tracks: Iterable[Track],
) -> ReconciliationResult:
    catalog_new = 0
    catalog_updated = 0
    catalog_unchanged = 0

    for track in tracks:
        norm_title, norm_artist = normalize_for_matching(track.title, track.artist)

        result = await session.execute(
            select(TrackCatalog).where(
                TrackCatalog.owner_id == owner_id,
                TrackCatalog.title_normalized == norm_title,
                TrackCatalog.artist_normalized == norm_artist,
            )
        )
        catalog = result.scalar_one_or_none()

        # Always compute data_quality on the immutable play ledger row.
        track.data_quality = _data_quality_for_track(track)

        if catalog is None:
            catalog = TrackCatalog(
                owner_id=owner_id,
                title=track.title,
                artist=track.artist,
                title_normalized=norm_title,
                artist_normalized=norm_artist,
                source="play_history",
                confidence="low",
                genre=track.genre,
                bpm=track.bpm,
                release_year=track.release_year,
                play_count=1,
                first_played=set_date,
                last_played=set_date,
            )
            session.add(catalog)
            await session.flush()

            # Confidence escalation for first play only happens via the "bpm + genre present" rule.
            catalog.confidence = _escalate_confidence(
                catalog.confidence,
                catalog.play_count,
                catalog_bpm=catalog.bpm,
                track_bpm=track.bpm,
                track_genre=track.genre,
            )

            track.catalog_id = catalog.id
            catalog_new += 1
            continue

        # Track is a play-unaltered ledger row; reconciliation links it to the best-known catalog.
        track.catalog_id = catalog.id

        before = (
            catalog.genre,
            catalog.bpm,
            catalog.release_year,
            catalog.confidence,
            catalog.source,
        )

        updated_any_metadata = False
        if track.genre is not None and catalog.genre is None:
            catalog.genre = track.genre
            updated_any_metadata = True
        if track.bpm is not None and catalog.bpm is None:
            catalog.bpm = track.bpm
            updated_any_metadata = True
        if track.release_year is not None and catalog.release_year is None:
            catalog.release_year = track.release_year
            updated_any_metadata = True

        if updated_any_metadata:
            catalog.source = "play_history"

        catalog.play_count += 1
        catalog.last_played = set_date

        catalog.confidence = _escalate_confidence(
            catalog.confidence,
            catalog.play_count,
            catalog_bpm=catalog.bpm,
            track_bpm=track.bpm,
            track_genre=track.genre,
        )

        after = (
            catalog.genre,
            catalog.bpm,
            catalog.release_year,
            catalog.confidence,
            catalog.source,
        )
        if after != before:
            catalog_updated += 1
        else:
            catalog_unchanged += 1

    return ReconciliationResult(
        catalog_new=catalog_new,
        catalog_updated=catalog_updated,
        catalog_unchanged=catalog_unchanged,
    )
