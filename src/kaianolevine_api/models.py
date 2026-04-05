from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    ARRAY,
    JSON,
    UUID,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Set(Base):
    __tablename__ = "sets"

    # TODO: add the following once a migration can be scheduled:
    # __table_args__ = (
    #     UniqueConstraint("owner_id", "source_file",
    #                      name="uq_sets_owner_source_file"),
    # )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    set_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    venue: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_file: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tracks: Mapped[list[Track]] = relationship(
        back_populates="set",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    catalog_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("track_catalog.id", ondelete="SET NULL"), nullable=True, index=True
    )

    play_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    play_time: Mapped[Time | None] = mapped_column(Time, nullable=True)

    # CSV column order (subset): label, title, remix, artist, comment, genre
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    remix: Mapped[str | None] = mapped_column(String, nullable=True)
    artist: Mapped[str] = mapped_column(String, nullable=False)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)

    genre: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # raw genre from CSV
    bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    length_secs: Mapped[int | None] = mapped_column(Integer, nullable=True)

    data_quality: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    set: Mapped[Set] = relationship(back_populates="tracks", lazy="selectin")
    catalog: Mapped[TrackCatalog | None] = relationship(lazy="selectin")


class TrackCatalog(Base):
    __tablename__ = "track_catalog"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    title: Mapped[str] = mapped_column(
        String, nullable=False
    )  # raw title from earliest known play
    artist: Mapped[str] = mapped_column(
        String, nullable=False
    )  # raw artist from earliest known play

    title_normalized: Mapped[str] = mapped_column(String, nullable=False)
    artist_normalized: Mapped[str] = mapped_column(String, nullable=False)

    remix: Mapped[str | None] = mapped_column(String, nullable=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)

    source: Mapped[str] = mapped_column(String, nullable=False, default="play_history")
    confidence: Mapped[str] = mapped_column(String, nullable=False, default="low")

    genre: Mapped[str | None] = mapped_column(String, nullable=True)
    bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    play_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_played: Mapped[Date] = mapped_column(Date, nullable=True)
    last_played: Mapped[Date] = mapped_column(Date, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "title_normalized",
            "artist_normalized",
            name="uq_track_catalog_owner_norm_title_artist",
        ),
    )


class PipelineEvaluation(Base):
    __tablename__ = "pipeline_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    repo: Mapped[str] = mapped_column(String, nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Legacy catch-all field. Prefer structured fields above.
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    finding: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    standards_version: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    flow_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evaluated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=False,
    )


class SpotifyPlaylist(Base):
    __tablename__ = "spotify_playlists"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    uri: Mapped[str] = mapped_column(String, nullable=False)
    playlist_type: Mapped[str] = mapped_column(
        "type",
        String,
        nullable=False,
        default="playlist",
        server_default="playlist",
    )
    public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    collaborative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    snapshot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    tracks_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class LivePlay(Base):
    __tablename__ = "live_plays"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    played_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    artist: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "title",
            "artist",
            "played_at",
            name="uq_live_plays_owner_title_artist_played_at",
        ),
    )


# ── WCS Notes ─────────────────────────────────────────────────────────────────


class WcsTranscript(Base):
    """Raw transcript storage. Retained for future RAG/embeddings corpus."""

    __tablename__ = "wcs_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String, nullable=False, default="unknown"
    )  # plaud | otter | zoom | google_meet | manual | unknown
    source_filename: Mapped[str] = mapped_column(String, nullable=False)
    drive_file_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    notes: Mapped[list[WcsNote]] = relationship(
        back_populates="transcript",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class WcsNote(Base):
    """Structured notes produced by the LLM from a WCS lesson transcript."""

    __tablename__ = "wcs_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wcs_transcripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    session_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    session_type: Mapped[str] = mapped_column(
        String, nullable=False, default="other"
    )  # private_lesson | group_class | other
    visibility: Mapped[str] = mapped_column(
        String, nullable=False, default="private"
    )  # private | public
    model: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    notes_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # PostgreSQL: TEXT[] (see migrations/011). SQLite tests: JSON via variant.
    instructors: Mapped[list[str]] = mapped_column(
        ARRAY(String).with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
    )
    students: Mapped[list[str]] = mapped_column(
        ARRAY(String).with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
    )
    organization: Mapped[str] = mapped_column(
        String, nullable=False, default="", server_default=""
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    transcript: Mapped[WcsTranscript] = relationship(
        back_populates="notes", lazy="selectin"
    )
