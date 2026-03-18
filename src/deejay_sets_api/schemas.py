from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Generic, Literal, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


class Meta(BaseModel):
    count: int = Field(..., ge=0)
    version: str


T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: Meta


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class SetListItem(BaseModel):
    id: uuid.UUID
    set_date: dt.date
    year: int
    venue: str
    source_file: str | None = None


class TrackListItem(BaseModel):
    id: uuid.UUID
    set_id: uuid.UUID
    set_date: dt.date
    venue: str

    play_order: int | None = None
    play_time: dt.time | None = None

    title: str
    artist: str
    genre: str | None = None
    bpm: float | None = None
    release_year: int | None = None
    length_secs: int | None = None

    data_quality: str | None = None
    catalog_id: uuid.UUID | None = None


class SetTrackListItem(TrackListItem):
    pass


class SetDetail(BaseModel):
    id: uuid.UUID
    set_date: dt.date
    year: int
    venue: str
    source_file: str | None = None
    tracks: list[SetTrackListItem]


class TrackDetail(TrackListItem):
    pass


ConfidenceLevel = Literal["low", "medium", "high"]
CatalogSource = Literal["play_history", "library", "vdj_history", "manual"]


class CatalogListItem(BaseModel):
    id: uuid.UUID
    title: str
    artist: str

    confidence: ConfidenceLevel
    source: CatalogSource

    genre: str | None = None
    bpm: float | None = None
    release_year: int | None = None

    play_count: int
    first_played: dt.date | None = None
    last_played: dt.date | None = None


class CatalogPatch(BaseModel):
    genre: str | None = None
    bpm: float | None = None
    release_year: int | None = None

    model_config = ConfigDict(extra="forbid")


class CatalogPlayHistoryItem(BaseModel):
    id: uuid.UUID
    set_id: uuid.UUID
    set_date: dt.date
    venue: str

    play_order: int | None = None
    play_time: dt.time | None = None

    data_quality: str | None = None


class CatalogDetail(BaseModel):
    id: uuid.UUID
    title: str
    artist: str

    confidence: ConfidenceLevel
    source: CatalogSource

    genre: str | None = None
    bpm: float | None = None
    release_year: int | None = None

    play_count: int
    first_played: dt.date | None = None
    last_played: dt.date | None = None

    play_history: list[CatalogPlayHistoryItem]


class EvaluationFinding(BaseModel):
    id: uuid.UUID | None = None
    repo: str
    dimension: str
    severity: str
    details: dict[str, Any] | str | None = None
    created_at: dt.datetime | None = None


class EvaluationCreateRequest(BaseModel):
    repo: str
    dimension: str
    severity: str
    details: dict[str, Any] | str | None = None

    model_config = ConfigDict(extra="forbid")


class EvaluationSummaryItem(BaseModel):
    severity: str
    dimension: str
    count: int


class StatsOverview(BaseModel):
    total_sets: int
    total_plays: int
    unique_tracks: int
    years_active: int
    most_played_artist: str | None = None


class StatsByYearItem(BaseModel):
    year: int
    set_count: int
    track_count: int


class StatsTopArtistItem(BaseModel):
    artist: str
    play_count: int


class StatsTopTrackItem(BaseModel):
    catalog_id: uuid.UUID
    title: str
    artist: str
    play_count: int


class IngestTrack(BaseModel):
    play_order: int | None = None
    play_time: dt.time | None = None

    title: str
    artist: str

    genre: str | None = None
    bpm: float | None = None
    release_year: int | None = None
    length_secs: int | None = None

    model_config = ConfigDict(extra="forbid")


class IngestSet(BaseModel):
    set_date: dt.date
    venue: str
    source_file: str
    tracks: list[IngestTrack]


class IngestResponseData(BaseModel):
    set_id: uuid.UUID
    tracks_created: int
    catalog_new: int
    catalog_updated: int
    catalog_unchanged: int


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    """
    Helper for raising errors with the standard `{ error: { code, message } }` envelope.
    """

    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def success_envelope(data: T, *, count: int, version: str) -> Envelope[T]:
    return Envelope(data=data, meta=Meta(count=count, version=version))
