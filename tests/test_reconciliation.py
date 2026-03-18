from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from deejay_sets_api.models import Set as DbSet
from deejay_sets_api.models import Track as DbTrack
from deejay_sets_api.models import TrackCatalog as DbCatalog
from deejay_sets_api.schemas import IngestTrack
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

        ingest_track1 = IngestTrack(
            play_order=None,
            play_time=None,
            title=raw_title,
            artist=raw_artist,
            genre=None,
            bpm=None,
            release_year=None,
            length_secs=None,
            label=None,
            remix=None,
            comment=None,
        )

        # First play: minimal payload (title+artist only).
        # Should low -> medium when play_count becomes 2.
        result1 = await reconcile_set_tracks(
            session=session,
            owner_id=owner_id,
            set_id=db_set.id,
            set_date=set_date,
            tracks=[ingest_track1],
        )
        await session.flush()
        assert result1.catalog_new == 0
        assert result1.catalog_updated == 1
        assert result1.catalog_unchanged == 0

        await session.refresh(catalog)
        assert catalog.play_count == 2
        assert catalog.confidence == "medium"

        track_rows = (
            (
                await session.execute(
                    select(DbTrack).where(DbTrack.set_id == db_set.id).order_by(DbTrack.id.asc())
                )
            )
            .scalars()
            .all()
        )
        assert len(track_rows) == 1
        assert track_rows[0].catalog_id == catalog.id
        assert track_rows[0].data_quality == "minimal"

        # Second play: provide BPM consistent within +/-2.
        # Should medium -> high when play_count becomes 3.
        ingest_track2 = IngestTrack(
            play_order=None,
            play_time=None,
            title=raw_title,
            artist=raw_artist,
            genre=None,
            bpm=101.0,
            release_year=None,
            length_secs=None,
            label=None,
            remix=None,
            comment=None,
        )

        # Second play: provide BPM consistent within +/-2.
        # Should medium -> high when play_count becomes 3.
        result2 = await reconcile_set_tracks(
            session=session,
            owner_id=owner_id,
            set_id=db_set.id,
            set_date=set_date,
            tracks=[ingest_track2],
        )
        await session.flush()
        assert result2.catalog_new == 0

        await session.refresh(catalog)
        assert catalog.play_count == 3
        assert catalog.confidence == "high"
        track_rows = (
            (
                await session.execute(
                    select(DbTrack).where(DbTrack.set_id == db_set.id).order_by(DbTrack.id.asc())
                )
            )
            .scalars()
            .all()
        )
        assert len(track_rows) == 2
        assert track_rows[1].catalog_id == catalog.id


async def test_reconciliation_data_quality_enrichment_fields(async_engine) -> None:
    owner_id = "dev-owner"
    sessionmaker = async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)

    set_date = date(2026, 3, 8)
    raw_title = "My Boo"
    raw_artist = "Artist"

    async with sessionmaker() as session:
        db_set = DbSet(owner_id=owner_id, set_date=set_date, venue="MADjam", source_file="test2.csv")
        session.add(db_set)
        await session.flush()

        ingest_minimal = IngestTrack(
            play_order=1,
            play_time=None,
            title=raw_title,
            artist=raw_artist,
            genre=None,
            bpm=None,
            release_year=None,
            length_secs=None,
            label=None,
            remix=None,
            comment=None,
        )
        ingest_partial = IngestTrack(
            play_order=2,
            play_time=None,
            title=raw_title,
            artist=raw_artist,
            genre="R&B",
            bpm=None,
            release_year=None,
            length_secs=None,
            label=None,
            remix=None,
            comment=None,
        )
        ingest_complete = IngestTrack(
            play_order=3,
            play_time=None,
            title=raw_title,
            artist=raw_artist,
            genre="R&B",
            bpm=100.0,
            release_year=2019,
            length_secs=180,
            label=None,
            remix=None,
            comment=None,
        )

        await reconcile_set_tracks(
            session=session,
            owner_id=owner_id,
            set_id=db_set.id,
            set_date=set_date,
            tracks=[ingest_minimal, ingest_partial, ingest_complete],
        )

        await session.flush()

        track_rows = (
            await session.execute(
                select(DbTrack)
                .where(DbTrack.set_id == db_set.id)
                .order_by(DbTrack.play_order.asc())
            )
        ).scalars().all()

        assert [t.data_quality for t in track_rows] == ["minimal", "partial", "complete"]
