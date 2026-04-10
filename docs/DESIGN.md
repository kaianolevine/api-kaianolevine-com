# DESIGN.md

## Architecture Overview

`kaianolevine-api` is a FastAPI service deployed on Railway. The production stack uses
SQLAlchemy async ORM with `asyncpg` against PostgreSQL. Tests run against an in-memory
SQLite database to keep CI fast and deterministic.

Write traffic is intentionally constrained: Prefect cogs are the only intended write
clients for ingest and automation pathways. User-facing read APIs expose sets, tracks,
catalog, notes, and stats. Runtime write surfaces for ingest and live plays are gated by
feature flags so ingestion can be paused without redeploying. Sentry is enabled in API
runtime (when configured) for centralized error tracking and observability.

## Section 5: API Endpoints

All endpoints return the standard success envelope:

`{ "data": ..., "meta": { "count": <n>, "total": <n>, "version": "<API_VERSION>" } }`

Errors return:

`{ "error": { "code": "...", "message": "..." } }`

### Sets

* `GET /v1/sets` — list sets (`year`, `venue`, `date_from`, `date_to`, `limit=50`, `offset=0`)
* `GET /v1/sets/{id}` — single set with full track list
* `GET /v1/sets/{id}/tracks` — ordered track list for a set

### Tracks

* `GET /v1/tracks` — query tracks (`artist`, `title`, `genre`, `bpm_min`, `bpm_max`, `year`, `data_quality`, `limit=50`, `offset=0`)
* `GET /v1/tracks/{id}` — single track play with set context

### Catalog

* `GET /v1/catalog` — list catalog entries (`artist`, `title`, `confidence`, `min_play_count`, `limit`, `offset`)
* `GET /v1/catalog/{id}` — catalog entry with play history
* `PATCH /v1/catalog/{id}` — update `genre`, `bpm`, `release_year` (source becomes `manual`); protected

### Evaluations

* `GET /v1/evaluations` — list findings (`repo`, `dimension`, `severity`, `limit`, `offset`)
* `GET /v1/evaluations/summary` — aggregate by severity and dimension
* `POST /v1/evaluations` — write findings; protected

### Stats

* `GET /v1/stats/overview`
* `GET /v1/stats/by-year`
* `GET /v1/stats/top-artists`
* `GET /v1/stats/top-tracks`

### Ingest

* `POST /v1/ingest` — accept a set with track list, run reconciliation, return set id + catalog stats; protected

## Reconciliation + Normalization

Normalization and reconciliation rules are implemented in:
* `src/kaianolevine_api/services/normalization.py`
* `src/kaianolevine_api/services/reconciliation.py`

