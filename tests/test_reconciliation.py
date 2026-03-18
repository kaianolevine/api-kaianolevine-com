from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker

from deejay_sets_api.models import Set as DbSet
from deejay_sets_api.models import Track as DbTrack
from deejay_sets_api.models import TrackCatalog as DbCatalog
from deejay_sets_api.services.normalization import normalize_for_matching
from deejay_sets_api.services.reconciliation import reconcile_set_tracks


async def test_reconciliation_confidence_escalation(async_engine) -> None:
    owner_id = "dev-owner"
    sessionmaker = async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)

    set_date = date(2026, 3, 8)
    raw_title = "My Boo"
    raw_artist = "Artist"
    title_norm, artist_norm = normalize_for_matching(raw_title, raw_artist)

    async with sessionmaker() as session:
        db_set = DbSet(owner_id=owner_id, set_date=set_date, venue="MADjam", source_file="test.csv")
        session.add(db_set)
        await session.flush()

        catalog = DbCatalog(
            owner_id=owner_id,
            title=raw_title,
            artist=raw_artist,
            title_normalized=title_norm,
            artist_normalized=artist_norm,
            source="play_history",
            confidence="low",
            genre="R&B",
            bpm=100.0,
            release_year=None,
            play_count=1,
            first_played=set_date,
            last_played=set_date,
        )
        session.add(catalog)
        await session.flush()

        # First play: minimal payload (title+artist only).
        # Should low -> medium when play_count becomes 2.
        track1 = DbTrack(
            owner_id=owner_id,
            set_id=db_set.id,
            catalog_id=None,
            play_order=None,
            play_time=None,
            title=raw_title,
            artist=raw_artist,
            genre=None,
            bpm=None,
            release_year=None,
            length_secs=None,
            data_quality=None,
        )
        session.add(track1)
        await session.flush()

        result1 = await reconcile_set_tracks(
            session=session, owner_id=owner_id, set_date=set_date, tracks=[track1]
        )
        await session.flush()
        assert result1.catalog_new == 0
        assert result1.catalog_updated == 1
        assert result1.catalog_unchanged == 0

        await session.refresh(catalog)
        assert catalog.play_count == 2
        assert catalog.confidence == "medium"
        assert track1.catalog_id == catalog.id
        assert track1.data_quality == "minimal"

        # Second play: provide BPM consistent within +/-2.
        # Should medium -> high when play_count becomes 3.
        track2 = DbTrack(
            owner_id=owner_id,
            set_id=db_set.id,
            catalog_id=None,
            play_order=None,
            play_time=None,
            title=raw_title,
            artist=raw_artist,
            genre=None,
            bpm=101.0,
            release_year=None,
            length_secs=None,
            data_quality=None,
        )
        session.add(track2)
        await session.flush()

        result2 = await reconcile_set_tracks(
            session=session, owner_id=owner_id, set_date=set_date, tracks=[track2]
        )
        await session.flush()
        assert result2.catalog_new == 0

        await session.refresh(catalog)
        assert catalog.play_count == 3
        assert catalog.confidence == "high"
        assert track2.catalog_id == catalog.id
