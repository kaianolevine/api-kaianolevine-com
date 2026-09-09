from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Generic, Literal, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Meta(BaseModel):
    """Pagination metadata included with every envelope response."""

    count: int = Field(..., ge=0, description="Number of items in this response.")
    total: int = Field(..., ge=0, description="Total number of matching items.")
    version: str = Field(..., description="API version string for this response.")


T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """TODO: describe this class."""

    data: T = Field(..., description="Semantic value for data.")
    meta: Meta = Field(..., description="Semantic value for meta.")


class ErrorDetail(BaseModel):
    """Structured error payload used across API error responses."""

    code: str = Field(..., description="Semantic value for code.")
    message: str = Field(..., description="Semantic value for message.")
    details: dict | list | str | None = Field(
        default=None, description="Semantic value for details."
    )


class ErrorEnvelope(BaseModel):
    """Top-level API error envelope."""

    error: ErrorDetail = Field(..., description="Semantic value for error.")


class SetListItem(BaseModel):
    """Summary view of one set returned by list endpoints."""

    id: uuid.UUID = Field(..., description="Unique identifier for this setlist.")
    set_date: dt.date = Field(..., description="Calendar date the set was played.")
    year: int = Field(..., description="Semantic value for year.")
    venue: str = Field(..., description="Venue name for the set or play.")
    source_file: str | None = Field(
        default=None, description="Semantic value for source file."
    )
    track_count: int = Field(default=0, description="Semantic value for track count.")


class TrackListItem(BaseModel):
    """TODO: describe this class."""

    id: uuid.UUID = Field(..., description="Unique identifier for this tracklist.")
    set_id: uuid.UUID = Field(..., description="Semantic value for set id.")
    set_date: dt.date = Field(..., description="Calendar date the set was played.")
    venue: str = Field(..., description="Venue name for the set or play.")

    play_order: int | None = Field(
        default=None, description="Semantic value for play order."
    )
    play_time: dt.time | None = Field(
        default=None, description="Semantic value for play time."
    )

    label: str | None = Field(default=None, description="Semantic value for label.")
    title: str = Field(..., description="Title value for this record.")
    remix: str | None = Field(default=None, description="Semantic value for remix.")
    artist: str = Field(..., description="Artist name associated with this record.")
    comment: str | None = Field(default=None, description="Semantic value for comment.")
    genre: str | None = Field(default=None, description="Semantic value for genre.")
    bpm: float | None = Field(default=None, description="Semantic value for bpm.")
    release_year: int | None = Field(
        default=None, description="Semantic value for release year."
    )
    length_secs: int | None = Field(
        default=None, description="Semantic value for length secs."
    )

    data_quality: str | None = Field(
        default=None, description="Semantic value for data quality."
    )
    catalog_id: uuid.UUID | None = Field(
        default=None, description="Semantic value for catalog id."
    )


class SetTrackListItem(TrackListItem):
    """Track list item returned when expanding a set."""

    pass


class SetDetail(BaseModel):
    """Detailed set payload including associated tracks."""

    id: uuid.UUID = Field(..., description="Unique identifier for this set.")
    set_date: dt.date = Field(..., description="Calendar date the set was played.")
    year: int = Field(..., description="Semantic value for year.")
    venue: str = Field(..., description="Venue name for the set or play.")
    source_file: str | None = Field(
        default=None, description="Semantic value for source file."
    )
    track_count: int = Field(default=0, description="Semantic value for track count.")
    tracks: list[SetTrackListItem] = Field(
        ..., description="Semantic value for tracks."
    )


class TrackDetail(TrackListItem):
    """Detailed track payload for a single track lookup."""

    pass


ConfidenceLevel = Literal["low", "medium", "high"]
CatalogSource = Literal["play_history", "library", "vdj_history", "manual"]


class CatalogListItem(BaseModel):
    """Catalog summary row for track-level search and listing."""

    id: uuid.UUID = Field(..., description="Unique identifier for this cataloglist.")
    title: str = Field(..., description="Title value for this record.")
    artist: str = Field(..., description="Artist name associated with this record.")

    confidence: ConfidenceLevel = Field(
        ..., description="Semantic value for confidence."
    )
    source: CatalogSource = Field(..., description="Semantic value for source.")

    genre: str | None = Field(default=None, description="Semantic value for genre.")
    bpm: float | None = Field(default=None, description="Semantic value for bpm.")
    release_year: int | None = Field(
        default=None, description="Semantic value for release year."
    )

    play_count: int = Field(
        ..., description="Number of plays recorded for this entity."
    )
    first_played: dt.date | None = Field(
        default=None, description="Semantic value for first played."
    )
    last_played: dt.date | None = Field(
        default=None, description="Semantic value for last played."
    )


class CatalogPatch(BaseModel):
    """Mutable catalog fields accepted by patch operations."""

    genre: str | None = Field(default=None, description="Semantic value for genre.")
    bpm: float | None = Field(default=None, description="Semantic value for bpm.")
    release_year: int | None = Field(
        default=None, description="Semantic value for release year."
    )

    model_config = ConfigDict(extra="forbid")


class CatalogPlayHistoryItem(BaseModel):
    """Catalog-linked play-history row from a source set."""

    id: uuid.UUID = Field(
        ..., description="Unique identifier for this catalogplayhistory."
    )
    set_id: uuid.UUID = Field(..., description="Semantic value for set id.")
    set_date: dt.date = Field(..., description="Calendar date the set was played.")
    venue: str = Field(..., description="Venue name for the set or play.")

    play_order: int | None = Field(
        default=None, description="Semantic value for play order."
    )
    play_time: dt.time | None = Field(
        default=None, description="Semantic value for play time."
    )

    data_quality: str | None = Field(
        default=None, description="Semantic value for data quality."
    )


class CatalogDetail(BaseModel):
    """Detailed catalog entry including play-history rows."""

    id: uuid.UUID = Field(..., description="Unique identifier for this catalog.")
    title: str = Field(..., description="Title value for this record.")
    artist: str = Field(..., description="Artist name associated with this record.")

    confidence: ConfidenceLevel = Field(
        ..., description="Semantic value for confidence."
    )
    source: CatalogSource = Field(..., description="Semantic value for source.")

    genre: str | None = Field(default=None, description="Semantic value for genre.")
    bpm: float | None = Field(default=None, description="Semantic value for bpm.")
    release_year: int | None = Field(
        default=None, description="Semantic value for release year."
    )

    play_count: int = Field(
        ..., description="Number of plays recorded for this entity."
    )
    first_played: dt.date | None = Field(
        default=None, description="Semantic value for first played."
    )
    last_played: dt.date | None = Field(
        default=None, description="Semantic value for last played."
    )

    play_history: list[CatalogPlayHistoryItem] = Field(
        ..., description="Semantic value for play history."
    )


class PipelineEvaluationCreate(BaseModel):
    """Payload for creating one pipeline evaluation finding."""

    run_id: str | None = Field(default=None, description="Semantic value for run id.")
    violation_id: str | None = Field(
        default=None, description="Semantic value for violation id."
    )
    repo: str = Field(..., description="Semantic value for repo.")
    dimension: str = Field(
        ..., description="Semantic value for dimension."
    )  # structural_conformance | pipeline_consistency |
    # testing_coverage | documentation_coverage |
    # cd_readiness | cross_repo_coherence | standards_currency
    severity: Literal["CRITICAL", "ERROR", "WARN", "INFO", "SUCCESS"] = Field(
        ..., description="Semantic value for severity."
    )
    finding: str = Field(..., description="Semantic value for finding.")
    suggestion: str | None = Field(
        default=None, description="Semantic value for suggestion."
    )
    standards_version: str | None = Field(
        default=None,
        description=(
            "Standards-version this finding was evaluated against. Only "
            "meaningful for conformance-evaluator paths (LLM and "
            "deterministic) which know the standards rev they ran against. "
            "Self-reported runs from pipeline cogs "
            "(source=flow_inline / flow_hook) don't run against any "
            "standards rev and leave this null. The previous default of "
            "'6.0' stamped a stale version onto every self-report, which "
            "then surfaced in Pipeline Health as 'Evaluated against: v6.0' "
            "for runs that hadn't been evaluated against any standards "
            "at all."
        ),
    )
    source: str | None = Field(default=None, description="Semantic value for source.")
    flow_name: str | None = Field(
        default=None, description="Semantic value for flow name."
    )

    model_config = ConfigDict(extra="forbid")


class PipelineEvaluationItem(BaseModel):
    """Pipeline evaluation record returned by API routes."""

    id: uuid.UUID = Field(
        ..., description="Unique identifier for this pipelineevaluation."
    )
    run_id: str | None = Field(..., description="Semantic value for run id.")
    violation_id: str | None = Field(
        default=None, description="Semantic value for violation id."
    )
    repo: str = Field(..., description="Semantic value for repo.")
    dimension: str = Field(..., description="Semantic value for dimension.")
    severity: str = Field(..., description="Semantic value for severity.")
    finding: str = Field(..., description="Semantic value for finding.")
    suggestion: str | None = Field(..., description="Semantic value for suggestion.")
    standards_version: str | None = Field(
        ..., description="Semantic value for standards version."
    )
    source: str | None = Field(default=None, description="Semantic value for source.")
    flow_name: str | None = Field(
        default=None, description="Semantic value for flow name."
    )
    evaluated_at: dt.datetime = Field(
        ..., description="Semantic value for evaluated at."
    )


class EvaluationSummaryItem(BaseModel):
    """Aggregate evaluation counts for one dimension."""

    dimension: str = Field(..., description="Semantic value for dimension.")
    error_count: int = Field(..., description="Semantic value for error count.")
    warn_count: int = Field(..., description="Semantic value for warn count.")
    info_count: int = Field(..., description="Semantic value for info count.")
    most_recent: dt.datetime | None = Field(
        ..., description="Semantic value for most recent."
    )


class FeatureFlagItem(BaseModel):
    """Feature flag record returned by flag routes."""

    id: uuid.UUID = Field(..., description="Unique identifier for this featureflag.")
    owner_id: str = Field(
        ..., description="Owner identity associated with this record."
    )
    name: str = Field(..., description="Human-readable name.")
    enabled: bool = Field(..., description="Whether this feature flag is enabled.")
    description: str | None = Field(
        default=None, description="Human-readable description for this record."
    )
    created_at: dt.datetime = Field(
        ..., description="Timestamp when this record was created."
    )
    updated_at: dt.datetime = Field(
        ..., description="Timestamp when this record was last updated."
    )


class FeatureFlagPatch(BaseModel):
    """Patch payload for updating a feature flag."""

    enabled: bool = Field(..., description="Whether this feature flag is enabled.")

    model_config = ConfigDict(extra="forbid")


class StatsOverview(BaseModel):
    """TODO: describe this class."""

    total_sets: int = Field(..., description="Semantic value for total sets.")
    total_plays: int = Field(..., description="Semantic value for total plays.")
    unique_tracks: int = Field(..., description="Semantic value for unique tracks.")
    years_active: int = Field(..., description="Semantic value for years active.")
    most_played_artist: str | None = Field(
        default=None, description="Semantic value for most played artist."
    )


class StatsByYearItem(BaseModel):
    """Yearly aggregate stats row for set and track counts."""

    year: int = Field(..., description="Semantic value for year.")
    set_count: int = Field(..., description="Semantic value for set count.")
    track_count: int = Field(..., description="Semantic value for track count.")


class StatsTopArtistItem(BaseModel):
    """Top-artist aggregate row."""

    artist: str = Field(..., description="Artist name associated with this record.")
    play_count: int = Field(
        ..., description="Number of plays recorded for this entity."
    )


class StatsTopTrackItem(BaseModel):
    """Top-track aggregate row."""

    catalog_id: uuid.UUID = Field(..., description="Semantic value for catalog id.")
    title: str = Field(..., description="Title value for this record.")
    artist: str = Field(..., description="Artist name associated with this record.")
    play_count: int = Field(
        ..., description="Number of plays recorded for this entity."
    )


class IngestTrack(BaseModel):
    """TODO: describe this class."""

    play_order: int | None = Field(
        default=None, description="Semantic value for play order."
    )
    play_time: dt.time | None = Field(
        default=None, description="Semantic value for play time."
    )

    label: str | None = Field(default=None, description="Semantic value for label.")
    title: str = Field(..., description="Title value for this record.")
    remix: str | None = Field(default=None, description="Semantic value for remix.")
    artist: str = Field(..., description="Artist name associated with this record.")
    comment: str | None = Field(default=None, description="Semantic value for comment.")

    genre: str | None = Field(default=None, description="Semantic value for genre.")
    bpm: float | None = Field(default=None, description="Semantic value for bpm.")
    release_year: int | None = Field(
        default=None, description="Semantic value for release year."
    )
    length_secs: int | None = Field(
        default=None, description="Semantic value for length secs."
    )

    model_config = ConfigDict(extra="forbid")


class IngestSet(BaseModel):
    """Payload for ingesting one DJ set and its tracks."""

    set_date: dt.date = Field(..., description="Calendar date the set was played.")
    venue: str = Field(..., description="Venue name for the set or play.")
    source_file: str = Field(..., description="Semantic value for source file.")
    tracks: list[IngestTrack] = Field(..., description="Semantic value for tracks.")


class IngestResponseData(BaseModel):
    """Result counters produced by set-ingest operations."""

    set_id: uuid.UUID = Field(..., description="Semantic value for set id.")
    tracks_created: int = Field(..., description="Semantic value for tracks created.")
    catalog_new: int = Field(..., description="Semantic value for catalog new.")
    catalog_updated: int = Field(..., description="Semantic value for catalog updated.")
    catalog_unchanged: int = Field(
        ..., description="Semantic value for catalog unchanged."
    )


class LivePlayIngest(BaseModel):
    """One live-play row accepted by ingest endpoints."""

    played_at: dt.datetime = Field(..., description="Semantic value for played at.")
    title: str = Field(..., description="Title value for this record.")
    artist: str = Field(..., description="Artist name associated with this record.")

    model_config = ConfigDict(extra="forbid")


class LivePlaysIngest(BaseModel):
    """Batch payload for live-play ingest."""

    plays: list[LivePlayIngest] = Field(..., description="Semantic value for plays.")

    model_config = ConfigDict(extra="forbid")


class LivePlayRecord(BaseModel):
    """Live-play row returned by recent-play endpoints."""

    id: uuid.UUID = Field(..., description="Unique identifier for this liveplayrecord.")
    played_at: dt.datetime = Field(..., description="Semantic value for played at.")
    title: str = Field(..., description="Title value for this record.")
    artist: str = Field(..., description="Artist name associated with this record.")
    created_at: dt.datetime = Field(
        ..., description="Timestamp when this record was created."
    )


class LivePlaysResponseData(BaseModel):
    """Ingest counters for live-play upsert operations."""

    inserted: int = Field(..., description="Semantic value for inserted.")
    skipped: int = Field(..., description="Semantic value for skipped.")


class SpotifyPlaylistItem(BaseModel):
    """Spotify playlist snapshot returned by list endpoints."""

    id: str = Field(..., description="Unique identifier for this spotifyplaylist.")
    name: str = Field(..., description="Human-readable name.")
    url: str = Field(..., description="Semantic value for url.")
    uri: str = Field(..., description="Semantic value for uri.")
    type: str = Field(..., description="Semantic value for type.")
    public: bool = Field(..., description="Semantic value for public.")
    collaborative: bool = Field(..., description="Semantic value for collaborative.")
    snapshot_id: str | None = Field(..., description="Semantic value for snapshot id.")
    tracks_total: int = Field(..., description="Semantic value for tracks total.")
    owner_id: str = Field(
        ..., description="Owner identity associated with this record."
    )
    owner_name: str | None = Field(..., description="Semantic value for owner name.")
    captured_at: dt.datetime = Field(..., description="Semantic value for captured at.")


class SpotifyPlaylistIngest(BaseModel):
    """One Spotify playlist payload accepted for ingest."""

    id: str = Field(
        ..., description="Unique identifier for this spotifyplaylistingest."
    )
    name: str = Field(..., description="Human-readable name.")
    url: str = Field(..., description="Semantic value for url.")
    uri: str = Field(..., description="Semantic value for uri.")
    type: str = Field(default="playlist", description="Semantic value for type.")
    public: bool = Field(default=True, description="Semantic value for public.")
    collaborative: bool = Field(
        default=False, description="Semantic value for collaborative."
    )
    snapshot_id: str | None = Field(
        default=None, description="Semantic value for snapshot id."
    )
    tracks_total: int = Field(default=0, description="Semantic value for tracks total.")
    owner_id: str = Field(
        ..., description="Owner identity associated with this record."
    )
    owner_name: str | None = Field(
        default=None, description="Semantic value for owner name."
    )

    model_config = ConfigDict(extra="forbid")


class SpotifyPlaylistsIngest(BaseModel):
    """Batch payload for Spotify playlist ingest."""

    playlists: list[SpotifyPlaylistIngest] = Field(
        ..., description="Semantic value for playlists."
    )

    model_config = ConfigDict(extra="forbid")


class SpotifyPlaylistsIngestResponse(BaseModel):
    """Ingest counters for Spotify playlist upserts."""

    upserted: int = Field(..., description="Semantic value for upserted.")
    unchanged: int = Field(..., description="Semantic value for unchanged.")


class PrefectWebhookPayload(BaseModel):
    """Prefect flow-state payload accepted by webhook endpoint."""

    flow_run_id: str | None = Field(
        default=None, description="Semantic value for flow run id."
    )
    flow_name: str | None = Field(
        default=None, description="Semantic value for flow name."
    )
    state_name: str | None = Field(
        default=None, description="Semantic value for state name."
    )
    state_type: str | None = Field(
        default=None, description="Semantic value for state type."
    )
    start_time: str | None = Field(
        default=None, description="Semantic value for start time."
    )
    end_time: str | None = Field(
        default=None, description="Semantic value for end time."
    )

    model_config = ConfigDict(extra="allow")


def api_error(
    status_code: int,
    code: str,
    message: str,
    details: dict | list | str | None = None,
) -> HTTPException:
    """
    Helper for raising errors with the standard `{ error: { code, message } }` envelope.
    """

    d: dict[str, str | dict | list | None] = {"code": code, "message": message}
    if details is not None:
        d["details"] = details
    return HTTPException(status_code=status_code, detail=d)


def success_envelope(data: T, *, count: int, total: int, version: str) -> Envelope[T]:
    """Build a standard success envelope with metadata."""
    return Envelope(data=data, meta=Meta(count=count, total=total, version=version))


# ── WCS Notes schemas ─────────────────────────────────────────────────────────

WcsSessionType = Literal[
    "private_lesson",
    "group_class",
    "other",
]

WcsSourceType = Literal[
    "plaud",
    "otter",
    "zoom",
    "google_meet",
    "manual",
    "unknown",
]

WcsVisibility = Literal["private", "public"]


class WcsTranscriptCreate(BaseModel):
    """POST /v1/wcs/transcripts — called by transcription-cog."""

    raw_text: str = Field(..., description="Semantic value for raw text.")
    source_type: WcsSourceType = Field(
        default="unknown", description="Semantic value for source type."
    )
    source_filename: str = Field(..., description="Semantic value for source filename.")
    drive_file_id: str = Field(..., description="Semantic value for drive file id.")

    model_config = ConfigDict(extra="forbid")


class WcsTranscriptItem(BaseModel):
    """Stored WCS transcript metadata returned by API routes."""

    id: uuid.UUID = Field(..., description="Unique identifier for this wcstranscript.")
    source_type: str = Field(..., description="Semantic value for source type.")
    source_filename: str = Field(..., description="Semantic value for source filename.")
    drive_file_id: str = Field(..., description="Semantic value for drive file id.")
    created_at: dt.datetime = Field(
        ..., description="Timestamp when this record was created."
    )


class WcsNoteCreate(BaseModel):
    """POST /v1/wcs/notes — called by transcription-cog."""

    transcript_id: str = Field(..., description="Semantic value for transcript id.")
    title: str | None = Field(default=None, description="Title value for this record.")
    session_date: str | None = Field(
        default=None, description="Semantic value for session date."
    )  # ISO-8601 date string from filename
    session_type: WcsSessionType = Field(
        default="other", description="Session type for this WCS note."
    )
    instructors: list[str] = Field(
        default_factory=list, description="Semantic value for instructors."
    )
    students: list[str] = Field(
        default_factory=list, description="Semantic value for students."
    )
    organization: str = Field(
        default="", description="Semantic value for organization."
    )
    visibility: WcsVisibility = Field(
        default="private", description="Visibility setting for this record."
    )
    model: str = Field(..., description="Semantic value for model.")
    provider: str = Field(..., description="Semantic value for provider.")
    notes_json: dict[str, Any] = Field(
        ..., description="Semantic value for notes json."
    )

    model_config = ConfigDict(extra="forbid")


class WcsNoteItem(BaseModel):
    """Structured WCS note payload returned by read endpoints."""

    id: uuid.UUID = Field(..., description="Unique identifier for this wcsnote.")
    transcript_id: uuid.UUID = Field(
        ..., description="Semantic value for transcript id."
    )
    title: str | None = Field(..., description="Title value for this record.")
    session_date: dt.date | None = Field(
        ..., description="Semantic value for session date."
    )
    session_type: str = Field(..., description="Session type for this WCS note.")
    instructors: list[str] = Field(..., description="Semantic value for instructors.")
    students: list[str] = Field(..., description="Semantic value for students.")
    organization: str = Field(..., description="Semantic value for organization.")
    is_default_visible: bool = Field(
        ..., description="Semantic value for is default visible."
    )
    visibility: str = Field(..., description="Visibility setting for this record.")
    model: str = Field(..., description="Semantic value for model.")
    provider: str = Field(..., description="Semantic value for provider.")
    notes_json: dict[str, Any] = Field(
        ..., description="Semantic value for notes json."
    )
    created_at: dt.datetime = Field(
        ..., description="Timestamp when this record was created."
    )


class WcsUserProfileOut(BaseModel):
    """Public shape of a WCS user profile record."""

    user_id: str = Field(..., description="Semantic value for user id.")
    email: str = Field(..., description="Semantic value for email.")
    display_name: str = Field(..., description="Semantic value for display name.")
    is_admin: bool = Field(..., description="Whether the user has WCS admin access.")
    created_at: dt.datetime = Field(
        ..., description="Timestamp when this record was created."
    )
    last_seen_at: dt.datetime = Field(
        ..., description="Semantic value for last seen at."
    )

    model_config = ConfigDict(from_attributes=True)


class WcsUserProfilePatch(BaseModel):
    """Admin patch payload for mutable WCS user fields."""

    is_admin: bool | None = Field(
        default=None, description="Whether the user has WCS admin access."
    )

    model_config = ConfigDict(extra="forbid")


class WcsNoteGrantOut(BaseModel):
    """Public shape of a note-grant record."""

    id: uuid.UUID = Field(
        ..., description="Unique identifier for this wcsnotegrantout."
    )
    user_id: str = Field(..., description="Semantic value for user id.")
    note_id: uuid.UUID = Field(..., description="Semantic value for note id.")
    granted_by: str = Field(..., description="Semantic value for granted by.")
    granted_at: dt.datetime = Field(..., description="Semantic value for granted at.")

    model_config = ConfigDict(from_attributes=True)


class WcsNoteGrantCreate(BaseModel):
    """Payload for creating a WCS note grant."""

    user_id: str = Field(..., description="Semantic value for user id.")
    note_id: uuid.UUID = Field(..., description="Semantic value for note id.")

    model_config = ConfigDict(extra="forbid")


class WcsMeUpsert(BaseModel):
    """Payload for upserting caller profile identity fields."""

    email: str = Field(default="", description="Semantic value for email.")
    display_name: str = Field(
        default="", description="Semantic value for display name."
    )

    model_config = ConfigDict(extra="forbid")


class WcsNoteDefaultVisiblePatch(BaseModel):
    """PATCH /v1/wcs/admin/notes/{note_id}/visibility — default catalog visibility."""

    is_default_visible: bool = Field(
        ..., description="Semantic value for is default visible."
    )

    model_config = ConfigDict(extra="forbid")


class WcsNoteAdminPatch(BaseModel):
    """PATCH /v1/wcs/admin/notes/{note_id} — admin partial-update of editable fields.

    Every field is optional; only provided fields are applied. Unset fields are
    left untouched so callers can patch a single value (e.g. just the title).
    """

    session_date: dt.date | None = Field(
        default=None, description="Date of the lesson/class session."
    )
    session_type: WcsSessionType | None = Field(
        default=None, description="Session type for this WCS note."
    )
    title: str | None = Field(default=None, description="Title of the note.")
    organization: str | None = Field(
        default=None, description="Organization associated with the session."
    )
    students: list[str] | None = Field(
        default=None, description="Students who attended the session."
    )
    instructors: list[str] | None = Field(
        default=None, description="Instructors who taught the session."
    )
    is_default_visible: bool | None = Field(
        default=None,
        description="Whether this note is visible to all signed-in users by default.",
    )

    model_config = ConfigDict(extra="forbid")


class WcsNotePatch(BaseModel):
    """PATCH /v1/wcs/notes/{id} — user-facing visibility toggle."""

    visibility: WcsVisibility = Field(
        ..., description="Visibility setting for this record."
    )

    model_config = ConfigDict(extra="forbid")


# ── WCS entity substrate (extraction payloads, canonical reads, corrections) ──


class WcsExtractionEntity(BaseModel):
    """One entity claim extracted from a source."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["concept", "technique", "pattern", "drill"] = Field(
        ...,
        description="Discriminator for the entity kind (concept, technique, pattern, drill).",
    )
    name: str = Field(min_length=1, description="Human-readable name.")
    prose: str = Field("", description="Free-text content for this row.")
    external_origin: dict | None = Field(
        None, description="Optional external attribution (book, video, etc.)."
    )


class WcsExtractionEntityDefinition(BaseModel):
    """Per-source vocabulary definition from extraction."""

    model_config = ConfigDict(extra="ignore")

    entity_name: str = Field(
        min_length=1, description="Display name of the WCS entity."
    )
    definition: str = Field(
        min_length=1,
        description="Definition prose attached to an entity for one source.",
    )


class WcsExtractionEntityRelation(BaseModel):
    """Cross-entity relation from extraction."""

    model_config = ConfigDict(extra="ignore")

    from_: str = Field(alias="from", min_length=1, description="From.")
    to: str = Field(min_length=1, description="To.")
    relation_kind: str = Field(
        min_length=1,
        description="Discriminator for the entity-to-entity relation type.",
    )
    prose: str = Field("", description="Free-text content for this row.")


class WcsExtractionDrillPurpose(BaseModel):
    """Drill purpose from extraction."""

    model_config = ConfigDict(extra="ignore")

    drill_name: str = Field(min_length=1, description="Drill name.")
    skill_description: str = Field(
        min_length=1, description="Free-text description of the skill."
    )
    focus_context: str = Field(
        "", description="Focus or context hint that scopes how this row applies."
    )


class WcsExtractionTechniqueRequirement(BaseModel):
    """Technique requirement from extraction."""

    model_config = ConfigDict(extra="ignore")

    technique_name: str = Field(min_length=1, description="Technique name.")
    skill_description: str = Field(
        min_length=1, description="Free-text description of the skill."
    )


class WcsExtractionCommonMistake(BaseModel):
    """Common mistake from extraction."""

    model_config = ConfigDict(extra="ignore")

    entity_name: str | None = Field(None, description="Display name of the WCS entity.")
    mistake: str = Field(min_length=1, description="Mistake.")
    correction: str = Field(min_length=1, description="Correction.")


class WcsExtractionCompetitionNote(BaseModel):
    """Competition note from extraction."""

    model_config = ConfigDict(extra="ignore")

    note: str = Field(min_length=1, description="Note.")
    entity_name: str | None = Field(None, description="Display name of the WCS entity.")
    context: str = Field("", description="Free-text context for the reference.")


class WcsExtractionReference(BaseModel):
    """Person reference from extraction."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, description="Human-readable name.")
    type: (
        Literal[
            "instructor",
            "teacher",
            "dancer",
            "judge",
            "competitor",
            "coach",
            "pro",
        ]
        | None
    ) = Field(None, description="Type.")
    context: str = Field("", description="Free-text context for the reference.")


class WcsExtractionRawOutput(BaseModel):
    """The full extraction payload produced by transcription-cog's prompt.

    Matches EXTRACTION_SCHEMA in transcription_cog/schema.py.
    """

    model_config = ConfigDict(extra="allow")  # forward-compatible

    title: str = Field("", description="Topic or display title.")
    summary: str = Field("", description="Summary.")
    entities: list[WcsExtractionEntity] = Field(
        default_factory=list, description="WCS entity rows attached to this response."
    )
    entity_definitions: list[WcsExtractionEntityDefinition] = Field(
        default_factory=list,
        description="Entity definitions.",
    )
    entity_relations: list[WcsExtractionEntityRelation] = Field(
        default_factory=list, description="Entity relations."
    )
    drill_purposes: list[WcsExtractionDrillPurpose] = Field(
        default_factory=list,
        description="Drill-to-purpose links sourced from this row.",
    )
    technique_requirements: list[WcsExtractionTechniqueRequirement] = Field(
        default_factory=list,
        description="Technique-to-requirement links sourced from this row.",
    )
    common_mistakes: list[WcsExtractionCommonMistake] = Field(
        default_factory=list, description="Common mistakes."
    )
    competition_notes: list[WcsExtractionCompetitionNote] = Field(
        default_factory=list, description="Competition notes."
    )
    student_observations: list[dict] = Field(
        default_factory=list, description="Student observations."
    )
    action_items: list[dict] = Field(default_factory=list, description="Action items.")
    quotes: list[dict] = Field(default_factory=list, description="Quotes.")
    references: list[WcsExtractionReference] = Field(
        default_factory=list,
        description="Bare-reference rows (instructors mentioned but not attributed).",
    )
    off_topic_notes: list[dict] = Field(
        default_factory=list, description="Off topic notes."
    )
    suggested_new_sections: list[dict] = Field(
        default_factory=list, description="Suggested new sections."
    )


class WcsSourceCreate(BaseModel):
    """Payload for POST /v1/wcs/sources."""

    transcript_id: uuid.UUID = Field(
        ..., description="Identifier of the upstream transcript."
    )
    title: str | None = Field(None, description="Topic or display title.")
    session_date: dt.date | None = Field(
        None, description="Calendar date of the lesson session."
    )
    session_type: str = Field(
        "other", description="Session type — e.g. private_lesson, group_class, other."
    )
    instructors_raw: list[str] = Field(
        default_factory=list,
        description="Verbatim upstream instructor names before alias resolution.",
    )
    students_raw: list[str] = Field(
        default_factory=list,
        description="Verbatim upstream student names before alias resolution.",
    )
    organization: str = Field(
        "", description="Organization, studio, or event context for the session."
    )
    visibility: str = Field(
        "private", description="Coarse access-control flag (private vs. public)."
    )
    is_default_visible: bool = Field(
        False, description="Whether the source is shown in the default catalog."
    )
    extractor_version: str = Field(..., description="Extractor version.")
    extractor_model: str = Field(..., description="Extractor model.")
    extractor_provider: str = Field(..., description="Extractor provider.")
    prompt_version: str = Field(..., description="Prompt version.")
    raw_output: WcsExtractionRawOutput = Field(
        ..., description="Raw upstream extraction payload, unparsed."
    )


class WcsEntityItem(BaseModel):
    """Canonical entity returned by wiki/read endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique identifier.")
    slug: str = Field(
        ..., description="Lowercase, hyphen-separated canonical identifier."
    )
    canonical_name: str = Field(
        ..., description="Canonical, post-collapse display name."
    )
    kind: str = Field(
        ...,
        description="Discriminator for the entity kind (concept, technique, pattern, drill).",
    )
    overview_md: str = Field(..., description="Overview md.")
    status: str = Field(
        ..., description="Lifecycle status flag (e.g., stub, draft, mature)."
    )
    external_origin: dict = Field(
        ..., description="Optional external attribution (book, video, etc.)."
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Variant names that resolve to this canonical row.",
    )


class WcsSourceAttributionItem(BaseModel):
    """Source attribution row for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique identifier.")
    source_id: uuid.UUID = Field(
        ..., description="Identifier of the WCS source this row belongs to."
    )
    entity_id: uuid.UUID = Field(
        ..., description="Identifier of the WCS entity this attribution is about."
    )
    instructor_id: uuid.UUID | None = Field(
        ..., description="Identifier of the WCS instructor."
    )
    attribution_kind: str = Field(
        ..., description="Discriminator for the attribution row type."
    )
    prose: str = Field(..., description="Free-text content for this row.")
    raw_term: str = Field(
        ..., description="Raw term string as it appeared in the upstream extraction."
    )
    position: int = Field(
        ..., description="Ordinal position of the row within its source."
    )
    drill_goal: str | None = Field(None, description="Drill goal.")
    drill_steps: list[str] | None = Field(None, description="Drill steps.")
    mistake_text: str | None = Field(None, description="Mistake text.")
    correction_text: str | None = Field(None, description="Correction text.")
    origin: str = Field(
        ..., description="Originating source or upstream attribution metadata."
    )
    entity_slug: str = Field("", description="Canonical slug of the attributed entity.")
    entity_name: str = Field(
        "", description="Canonical display name of the attributed entity."
    )
    entity_kind: str = Field(
        "",
        description="Kind of the attributed entity (concept|technique|pattern|drill).",
    )
    instructor_slug: str | None = Field(
        None, description="Canonical slug of the attributing instructor, if linked."
    )
    instructor_name: str | None = Field(
        None,
        description="Canonical display name of the attributing instructor, if linked.",
    )


class WcsEntityRelationItem(BaseModel):
    """Entity relation row for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique identifier.")
    from_entity_id: uuid.UUID = Field(..., description="From entity id.")
    to_entity_id: uuid.UUID = Field(..., description="To entity id.")
    relation_kind: str = Field(
        ..., description="Discriminator for the entity-to-entity relation type."
    )
    source_id: uuid.UUID | None = Field(
        ..., description="Identifier of the WCS source this row belongs to."
    )
    prose: str = Field(..., description="Free-text content for this row.")
    origin: str = Field(
        ..., description="Originating source or upstream attribution metadata."
    )
    from_entity_slug: str = Field("", description="Canonical slug of the from-entity.")
    from_entity_name: str = Field(
        "", description="Canonical display name of the from-entity."
    )
    from_entity_kind: str = Field("", description="Kind of the from-entity.")
    to_entity_slug: str = Field("", description="Canonical slug of the to-entity.")
    to_entity_name: str = Field(
        "", description="Canonical display name of the to-entity."
    )
    to_entity_kind: str = Field("", description="Kind of the to-entity.")


class WcsDrillPurposeItem(BaseModel):
    """Drill purpose row for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique identifier.")
    drill_entity_id: uuid.UUID = Field(..., description="Drill entity id.")
    source_id: uuid.UUID | None = Field(
        ..., description="Identifier of the WCS source this row belongs to."
    )
    skill_name: str = Field(
        ..., description="Human-readable skill name this row references."
    )
    skill_slug: str = Field(..., description="Skill slug.")
    prose: str = Field(..., description="Free-text content for this row.")
    focus_context: str = Field(
        ..., description="Focus or context hint that scopes how this row applies."
    )
    origin: str = Field(
        ..., description="Originating source or upstream attribution metadata."
    )
    drill_entity_slug: str = Field(
        "", description="Canonical slug of the drill entity."
    )
    drill_entity_name: str = Field(
        "", description="Canonical display name of the drill entity."
    )


class WcsTechniqueRequirementItem(BaseModel):
    """Technique requirement row for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique identifier.")
    technique_entity_id: uuid.UUID = Field(..., description="Technique entity id.")
    source_id: uuid.UUID | None = Field(
        ..., description="Identifier of the WCS source this row belongs to."
    )
    skill_name: str = Field(
        ..., description="Human-readable skill name this row references."
    )
    skill_slug: str = Field(..., description="Skill slug.")
    prose: str = Field(..., description="Free-text content for this row.")
    origin: str = Field(
        ..., description="Originating source or upstream attribution metadata."
    )
    technique_entity_slug: str = Field(
        "", description="Canonical slug of the technique entity."
    )
    technique_entity_name: str = Field(
        "", description="Canonical display name of the technique entity."
    )


class WcsEntityDefinitionItem(BaseModel):
    """Entity definition row for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique identifier.")
    entity_id: uuid.UUID = Field(..., description="Identifier of the WCS entity.")
    source_id: uuid.UUID = Field(
        ..., description="Identifier of the WCS source this row belongs to."
    )
    instructor_id: uuid.UUID | None = Field(
        ..., description="Identifier of the WCS instructor."
    )
    term: str = Field(..., description="Term.")
    definition: str = Field(
        ..., description="Definition prose attached to an entity for one source."
    )
    position: int = Field(
        ..., description="Ordinal position of the row within its source."
    )
    origin: str = Field(
        ..., description="Originating source or upstream attribution metadata."
    )
    entity_slug: str = Field("", description="Canonical slug of the defined entity.")
    entity_name: str = Field(
        "", description="Canonical display name of the defined entity."
    )
    entity_kind: str = Field("", description="Kind of the defined entity.")
    instructor_slug: str | None = Field(
        None, description="Canonical slug of the defining instructor, if linked."
    )
    instructor_name: str | None = Field(
        None,
        description="Canonical display name of the defining instructor, if linked.",
    )


class WcsInstructorItem(BaseModel):
    """Instructor row for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique identifier.")
    slug: str = Field(
        ..., description="Lowercase, hyphen-separated canonical identifier."
    )
    canonical_name: str = Field(
        ..., description="Canonical, post-collapse display name."
    )
    background_md: str = Field(..., description="Background md.")
    teaching_themes_md: str = Field(..., description="Teaching themes md.")
    notable_framings_md: str = Field(..., description="Notable framings md.")
    aliases: list[str] = Field(
        default_factory=list,
        description="Variant names that resolve to this canonical row.",
    )


class WcsSourceDefaultVisiblePatch(BaseModel):
    """PATCH /v1/wcs/admin/sources/{source_id}/visibility — default catalog visibility."""

    is_default_visible: bool = Field(
        ..., description="Semantic value for is default visible."
    )

    model_config = ConfigDict(extra="forbid")


class WcsSourceAdminPatch(BaseModel):
    """PATCH /v1/wcs/admin/sources/{source_id} — admin partial-update of editable fields.

    Every field is optional; only provided fields are applied. Unset fields are
    left untouched so callers can patch a single value (e.g. just the title).
    """

    session_date: dt.date | None = Field(
        default=None, description="Date of the lesson/class session."
    )
    session_type: str | None = Field(
        default=None, description="Session type for this WCS source."
    )
    title: str | None = Field(default=None, description="Title of the source.")
    organization: str | None = Field(
        default=None, description="Organization associated with the session."
    )
    students_raw: list[str] | None = Field(
        default=None, description="Students who attended the session."
    )
    instructors_raw: list[str] | None = Field(
        default=None, description="Instructors who taught the session."
    )
    is_default_visible: bool | None = Field(
        default=None,
        description="Whether this source is visible to all signed-in users by default.",
    )

    model_config = ConfigDict(extra="forbid")


class WcsSourceItem(BaseModel):
    """Source row for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique identifier.")
    transcript_id: uuid.UUID = Field(
        ..., description="Identifier of the upstream transcript."
    )
    title: str | None = Field(..., description="Topic or display title.")
    session_date: dt.date | None = Field(
        ..., description="Calendar date of the lesson session."
    )
    session_type: str = Field(
        ..., description="Session type — e.g. private_lesson, group_class, other."
    )
    instructors_raw: list[str] = Field(
        ..., description="Verbatim upstream instructor names before alias resolution."
    )
    students_raw: list[str] = Field(
        ..., description="Verbatim upstream student names before alias resolution."
    )
    organization: str = Field(
        ..., description="Organization, studio, or event context for the session."
    )
    visibility: str = Field(
        ..., description="Coarse access-control flag (private vs. public)."
    )
    is_default_visible: bool = Field(
        ..., description="Whether the source is shown in the default catalog."
    )
    created_at: dt.datetime = Field(..., description="Timestamp this row was created.")


class WcsNameCorrectionCreate(BaseModel):
    """Payload for POST name correction admin endpoint."""

    raw_name: str = Field(
        min_length=1, description="Raw upstream name as it appeared before correction."
    )
    corrected_name: str = Field(
        min_length=1, description="Corrected name to apply in place of the raw form."
    )
    scope: Literal["global", "source"] = Field(
        "global",
        description="Application scope of the correction (global vs. per-source).",
    )
    source_id: uuid.UUID | None = Field(
        None, description="Identifier of the WCS source this row belongs to."
    )
    reason: str = Field("", description="Free-text rationale supplied by the admin.")


class WcsAttributionCorrectionCreate(BaseModel):
    """Payload for POST attribution correction admin endpoint."""

    source_id: uuid.UUID = Field(
        ..., description="Identifier of the WCS source this row belongs to."
    )
    attribution_target: dict = Field(
        ...,
        description="Locator (raw_term + position) of the attribution row to correct.",
    )
    field: str = Field(..., description="Name of the field being corrected.")
    corrected_value: dict = Field(
        ..., description="New value to apply for the corrected field."
    )
    reason: str = Field("", description="Free-text rationale supplied by the admin.")


class WcsSourceMetadataCorrectionCreate(BaseModel):
    """Payload for POST source metadata correction admin endpoint."""

    source_id: uuid.UUID = Field(
        ..., description="Identifier of the WCS source this row belongs to."
    )
    field: str = Field(..., description="Name of the field being corrected.")
    corrected_value: dict = Field(
        ..., description="New value to apply for the corrected field."
    )
    reason: str = Field("", description="Free-text rationale supplied by the admin.")


class WcsAttributionAdditionCreate(BaseModel):
    """Payload for POST attribution addition admin endpoint."""

    source_id: uuid.UUID | None = Field(
        None, description="Identifier of the WCS source this row belongs to."
    )
    entity_slug: str = Field(..., description="Slug of the WCS entity.")
    instructor_slug: str | None = Field(None, description="Slug of the WCS instructor.")
    attribution_kind: str = Field(
        "taught", description="Discriminator for the attribution row type."
    )
    prose: str = Field("", description="Free-text content for this row.")
    reason: str = Field("", description="Free-text rationale supplied by the admin.")


class WcsDrillPurposeAdditionCreate(BaseModel):
    """Payload for POST drill purpose addition admin endpoint."""

    drill_entity_slug: str = Field(
        ..., description="Slug of the drill entity this row attaches to."
    )
    source_id: uuid.UUID | None = Field(
        None, description="Identifier of the WCS source this row belongs to."
    )
    skill_name: str = Field(
        ..., description="Human-readable skill name this row references."
    )
    prose: str = Field("", description="Free-text content for this row.")
    focus_context: str = Field(
        "", description="Focus or context hint that scopes how this row applies."
    )
    reason: str = Field("", description="Free-text rationale supplied by the admin.")


class WcsTechniqueRequirementAdditionCreate(BaseModel):
    """Payload for POST technique requirement addition admin endpoint."""

    technique_entity_slug: str = Field(
        ..., description="Slug of the technique entity this row attaches to."
    )
    source_id: uuid.UUID | None = Field(
        None, description="Identifier of the WCS source this row belongs to."
    )
    skill_name: str = Field(
        ..., description="Human-readable skill name this row references."
    )
    prose: str = Field("", description="Free-text content for this row.")
    reason: str = Field("", description="Free-text rationale supplied by the admin.")


class WcsEntityRelationAdditionCreate(BaseModel):
    """Payload for POST entity relation addition admin endpoint."""

    from_entity_slug: str = Field(
        ..., description="Slug of the source entity in this relation."
    )
    to_entity_slug: str = Field(
        ..., description="Slug of the target entity in this relation."
    )
    relation_kind: str = Field(
        ..., description="Discriminator for the entity-to-entity relation type."
    )
    prose: str = Field("", description="Free-text content for this row.")
    reason: str = Field("", description="Free-text rationale supplied by the admin.")


class WcsSourceReferenceItem(BaseModel):
    """A person mentioned in a source. Stored as a raw name with context;
    not linked to canonical instructor records."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique identifier.")
    source_id: uuid.UUID = Field(
        ..., description="Identifier of the WCS source this row belongs to."
    )
    referenced_name: str = Field(
        ..., description="Raw mention name from the extraction."
    )
    context: str = Field(..., description="Free-text context for the reference.")
    ref_type: str = Field(..., description="Ref type.")
    origin: str = Field(
        ..., description="Originating source or upstream attribution metadata."
    )
    created_at: dt.datetime = Field(
        ..., description="Timestamp when this record was created."
    )


class WcsEntityViewItem(BaseModel):
    """Full entity view with attributions, definitions, relations, skill layer."""

    entity: WcsEntityItem = Field(..., description="Entity.")
    attributions: list[WcsSourceAttributionItem] = Field(
        default_factory=list,
        description="Attributions sourced from this row's parent record.",
    )
    definitions: list[WcsEntityDefinitionItem] = Field(
        default_factory=list,
        description="Definitions sourced from this row's parent record.",
    )
    relations_from: list[WcsEntityRelationItem] = Field(
        default_factory=list, description="Relations from."
    )
    relations_to: list[WcsEntityRelationItem] = Field(
        default_factory=list, description="Relations to."
    )
    drill_purposes: list[WcsDrillPurposeItem] = Field(
        default_factory=list,
        description="Drill-to-purpose links sourced from this row.",
    )
    technique_requirements: list[WcsTechniqueRequirementItem] = Field(
        default_factory=list,
        description="Technique-to-requirement links sourced from this row.",
    )


class WcsInstructorViewItem(BaseModel):
    """Full instructor view with attributions, definitions, and references."""

    instructor: WcsInstructorItem = Field(..., description="Instructor.")
    attributions: list[WcsSourceAttributionItem] = Field(
        default_factory=list,
        description="Attributions sourced from this row's parent record.",
    )
    definitions: list[WcsEntityDefinitionItem] = Field(
        default_factory=list,
        description="Definitions sourced from this row's parent record.",
    )
    referenced_in: list[WcsSourceReferenceItem] = Field(
        default_factory=list,
        description="Deprecated: references are no longer linked to instructors.",
    )


class WcsSourceViewItem(BaseModel):
    """Full source view with all canonical rows derived from it."""

    source: WcsSourceItem = Field(..., description="Source.")
    attributions: list[WcsSourceAttributionItem] = Field(
        default_factory=list,
        description="Attributions sourced from this row's parent record.",
    )
    definitions: list[WcsEntityDefinitionItem] = Field(
        default_factory=list,
        description="Definitions sourced from this row's parent record.",
    )
    relations: list[WcsEntityRelationItem] = Field(
        default_factory=list,
        description="Entity-to-entity relations sourced from this row.",
    )
    drill_purposes: list[WcsDrillPurposeItem] = Field(
        default_factory=list,
        description="Drill-to-purpose links sourced from this row.",
    )
    technique_requirements: list[WcsTechniqueRequirementItem] = Field(
        default_factory=list,
        description="Technique-to-requirement links sourced from this row.",
    )
    references: list[WcsSourceReferenceItem] = Field(
        default_factory=list,
        description="People mentioned in the source (raw names, not attributed).",
    )


class WcsWikiExportItem(BaseModel):
    """Bulk corpus export for wiki-curator-cog."""

    entities: list[WcsEntityItem] = Field(
        ..., description="WCS entity rows attached to this response."
    )
    instructors: list[WcsInstructorItem] = Field(
        ..., description="Instructor rows attached to this response."
    )
    sources: list[WcsSourceItem] = Field(
        ..., description="Source rows attached to this response."
    )
    attributions: list[WcsSourceAttributionItem] = Field(
        ..., description="Attributions sourced from this row's parent record."
    )
    definitions: list[WcsEntityDefinitionItem] = Field(
        ..., description="Definitions sourced from this row's parent record."
    )
    relations: list[WcsEntityRelationItem] = Field(
        ..., description="Entity-to-entity relations sourced from this row."
    )
    drill_purposes: list[WcsDrillPurposeItem] = Field(
        ..., description="Drill-to-purpose links sourced from this row."
    )
    technique_requirements: list[WcsTechniqueRequirementItem] = Field(
        ..., description="Technique-to-requirement links sourced from this row."
    )
    references: list[WcsSourceReferenceItem] = Field(
        ...,
        description="People mentioned in sources (raw names, not attributed).",
    )
    exported_at: dt.datetime = Field(..., description="Exported at.")


class WcsAdminCorrectionResult(BaseModel):
    """Result of an admin correction or addition write."""

    id: uuid.UUID = Field(..., description="Unique identifier.")
    field: str | None = Field(None, description="Name of the field being corrected.")
    recomposed_source_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="IDs of sources recomposed as a side effect of this action.",
    )
    deferred: bool = Field(
        False,
        description="Whether the action was deferred (e.g., global correction pending recompose).",
    )
    message: str = Field(
        "", description="Human-readable message describing the result."
    )


class WcsRecomposeResult(BaseModel):
    """Result of a manual compose_source run."""

    source_id: uuid.UUID = Field(
        ..., description="Identifier of the WCS source this row belongs to."
    )
    attributions_written: int = Field(
        ..., description="Number of attribution rows written."
    )
    definitions_written: int = Field(
        ..., description="Number of definition rows written."
    )
    relations_written: int = Field(..., description="Number of relation rows written.")
    drill_purposes_written: int = Field(
        ..., description="Number of drill-purpose rows written."
    )
    technique_requirements_written: int = Field(
        ..., description="Number of technique-requirement rows written."
    )
    references_written: int = Field(
        ..., description="Number of reference rows written."
    )


class WcsGapItem(BaseModel):
    """Lightweight curation gap descriptor."""

    slug: str = Field(
        ..., description="Lowercase, hyphen-separated canonical identifier."
    )
    name: str = Field(..., description="Human-readable name.")
    kind: str | None = Field(
        None,
        description="Discriminator for the entity kind (concept, technique, pattern, drill).",
    )
    count: int = Field(0, description="Number of items in this response.")
    detail: str = Field("", description="Free-text detail about the gap finding.")


class WhoamiVerifiedOut(BaseModel):
    """What verify saw about the presented credential, before resolve."""

    issuer: str = Field(..., description="Issuer that vouched for this credential.")
    subject: str = Field(
        ...,
        description=(
            "The exact subject string to seed into identity_principals. This "
            "is the one value the endpoint exists to report."
        ),
    )
    kind: str = Field(
        ..., description="Credential class the router selected: human or machine."
    )


class WhoamiPrincipalOut(BaseModel):
    """The principal this ecosystem has for the verified subject, if any."""

    id: str = Field(..., description="Principal id in identity_principals.")
    kind: str = Field(..., description="Semantic value for kind.")
    display_name: str = Field(..., description="Semantic value for display name.")
    status: str = Field(..., description="Semantic value for status.")
    roles: list[str] = Field(..., description="Roles held by this principal.")


class WhoamiOut(BaseModel):
    """Diagnostic view of verify and resolve for the calling credential.

    ``principal`` is null when no row exists for the verified subject —
    the expected state for a newly created machine, and the case this
    endpoint exists to make legible.
    """

    enforcement_point: str = Field(
        ..., description="Which enforcement point answered this request."
    )
    verified: WhoamiVerifiedOut = Field(
        ..., description="What verify established about the credential."
    )
    principal: WhoamiPrincipalOut | None = Field(
        None, description="Resolved principal, or null when none exists yet."
    )
    hint: str = Field(
        ..., description="Next action in prose, for whoever is wiring a principal."
    )


# ── Notifications ─────────────────────────────────────────────────────────────


class NotificationResult(BaseModel):
    """What the notification routes decided about one inbound event.

    Returned for drops as well as sends. GitHub gets a 200 either way, so the
    body is the only place the reason is visible to whoever is reading a
    delivery in GitHub's UI.
    """

    forwarded: bool = Field(
        ..., description="Whether the message reached the Discord webhook."
    )
    event: str = Field(..., description="GitHub event name, or 'notify'.")
    outcome: str | None = Field(
        default=None,
        description="Run conclusion or commit-status state, when the payload had one.",
    )
    reason: str = Field(
        ..., description="Why it was forwarded or dropped, in one token."
    )


class NotifyRequest(BaseModel):
    """An ad-hoc Discord message from first-party code.

    Deliberately Discord's own message shape rather than an abstraction over
    it. A wrapper would have to grow a field every time a caller wanted one
    Discord already has, and the callers are all in this ecosystem — there is
    no second transport to stay portable for.
    """

    content: str | None = Field(
        default=None,
        max_length=2000,
        description="Message text. Discord's own limit is 2000 characters.",
    )
    embeds: list[dict[str, Any]] | None = Field(
        default=None,
        max_length=10,
        description="Discord embed objects, passed through unmodified.",
    )
    username: str | None = Field(
        default=None,
        max_length=80,
        description="Override the webhook's display name for this message.",
    )

    @model_validator(mode="after")
    def require_a_body(self) -> NotifyRequest:
        """Reject a message with nothing in it — Discord would 400 anyway."""
        if not self.content and not self.embeds:
            raise ValueError("one of content or embeds is required")
        return self

    def to_discord(self) -> dict[str, Any]:
        """Render the Discord webhook body, omitting anything unset."""
        payload: dict[str, Any] = {}
        if self.content:
            payload["content"] = self.content
        if self.embeds:
            payload["embeds"] = self.embeds
        if self.username:
            payload["username"] = self.username
        return payload


# ── GitHub repo status dashboard ──────────────────────────────────────────────
#
# Shapes for GET /v1/github/status. The route is public, so these models are
# also the disclosure boundary: there is no field here that could carry a
# private repository's name, URL, description, branch, or any issue or PR
# title. Private repos reach the page only through GithubPrivateSummary,
# which holds nothing but counts.

GithubBuildState = Literal["success", "failure", "error", "pending", "none"]

GithubPrivateDisclosure = Literal["aggregate", "hidden", "full"]


class GithubBuildCounts(BaseModel):
    """How many repos sit in each build state."""

    success: int = Field(0, ge=0, description="Default branch checks all passing.")
    failure: int = Field(0, ge=0, description="At least one required check failing.")
    error: int = Field(0, ge=0, description="A check errored rather than failed.")
    pending: int = Field(
        0, ge=0, description="Checks queued, running, or not yet reported."
    )
    none: int = Field(
        0, ge=0, description="Head commit has no checks at all — not a pass."
    )


class GithubRepoStatus(BaseModel):
    """One listed repository. Only ever a public repo unless the committed
    config sets `private_repos: full`."""

    org: str = Field(..., description="Owning organization login.")
    name: str = Field(..., description="Repository name, without the org prefix.")
    url: str = Field(..., description="Canonical GitHub URL.")
    description: str | None = Field(None, description="Repository description.")
    language: str | None = Field(None, description="Primary language, per GitHub.")
    default_branch: str | None = Field(
        None, description="Default branch name; null if the repo is empty."
    )
    build: GithubBuildState = Field(
        ..., description="Check rollup on the default branch's head commit."
    )
    open_pull_requests: int = Field(0, ge=0, description="Open PR count.")
    open_issues: int = Field(
        0, ge=0, description="Open issue count, excluding pull requests."
    )
    branches: int = Field(
        0,
        ge=0,
        description="Branches on the repo — every ref under refs/heads, default branch included.",
    )
    pushed_at: dt.datetime | None = Field(
        None, description="Last push to any branch, per GitHub."
    )


class GithubPrivateSummary(BaseModel):
    """The whole of what a private repository discloses on a public page."""

    repo_count: int = Field(0, ge=0, description="How many private repos were counted.")
    builds: GithubBuildCounts = Field(
        ..., description="Build states across those repos."
    )
    open_pull_requests: int = Field(0, ge=0, description="Open PRs across those repos.")
    open_issues: int = Field(0, ge=0, description="Open issues across those repos.")
    branches: int = Field(0, ge=0, description="Branches across those repos.")


class GithubOrgSummary(BaseModel):
    """Per-organization roll-up shown above that org's repositories."""

    login: str = Field(..., description="Organization login.")
    listed_repo_count: int = Field(
        0, ge=0, description="Repositories listed individually for this org."
    )
    private: GithubPrivateSummary | None = Field(
        None,
        description="Counts for this org's private repos; null when there are none or they are hidden.",
    )


GithubOrgFailureReason = Literal[
    "unauthorized",
    "not_found_or_no_access",
    "rate_limited",
    "unreachable",
]


class GithubOrgError(BaseModel):
    """An organization that could not be read on this refresh.

    The reason is a coarse category on purpose. GitHub's own error text can
    echo query internals and logins the reader has no business seeing, and
    this route is public — the detail belongs in the logs, not here.
    """

    login: str = Field(..., description="Organization login that could not be read.")
    reason: GithubOrgFailureReason = Field(
        ..., description="Why it could not be read, at a public-safe granularity."
    )


class GithubTotals(BaseModel):
    """Headline numbers spanning listed and aggregated repositories alike."""

    repositories: int = Field(0, ge=0, description="Every repo counted, listed or not.")
    open_pull_requests: int = Field(0, ge=0, description="Open PRs across the fleet.")
    open_issues: int = Field(0, ge=0, description="Open issues across the fleet.")
    branches: int = Field(0, ge=0, description="Branches across the fleet.")
    builds: GithubBuildCounts = Field(..., description="Build states across the fleet.")


class GithubStatus(BaseModel):
    """The dashboard payload."""

    fetched_at: dt.datetime = Field(
        ...,
        description="When this snapshot was read from GitHub — not when it was served.",
    )
    stale: bool = Field(
        False,
        description="True when GitHub could not be reached and a previous snapshot is being served.",
    )
    cache_ttl_seconds: int = Field(
        ...,
        ge=0,
        description="How long a snapshot is served before GitHub is called again.",
    )
    private_disclosure: GithubPrivateDisclosure = Field(
        ..., description="How private repos are represented in this payload."
    )
    orgs: list[GithubOrgSummary] = Field(
        default_factory=list, description="Per-organization summaries."
    )
    repositories: list[GithubRepoStatus] = Field(
        default_factory=list,
        description="Listed repositories, worst build state first.",
    )
    unavailable_orgs: list[GithubOrgError] = Field(
        default_factory=list,
        description=(
            "Organizations skipped on this refresh. A non-empty list means the "
            "totals below cover less than the configured fleet."
        ),
    )
    totals: GithubTotals = Field(..., description="Fleet-wide headline numbers.")
