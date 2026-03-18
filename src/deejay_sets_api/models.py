from __future__ import annotations

import uuid

from sqlalchemy import (
    UUID,
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

    play_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    play_time: Mapped[Time | None] = mapped_column(Time, nullable=True)

    title: Mapped[str] = mapped_column(String, nullable=False)
    artist: Mapped[str] = mapped_column(String, nullable=False)

    genre: Mapped[str | None] = mapped_column(String, nullable=True)  # raw genre from CSV
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

    title: Mapped[str] = mapped_column(String, nullable=False)  # raw title from earliest known play
    artist: Mapped[str] = mapped_column(
        String, nullable=False
    )  # raw artist from earliest known play

    title_normalized: Mapped[str] = mapped_column(String, nullable=False)
    artist_normalized: Mapped[str] = mapped_column(String, nullable=False)

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

    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
