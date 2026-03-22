# 1.0.0 (2026-03-22)


### Bug Fixes

* add missing endpoints to CORS documentation ([3175cd6](https://github.com/kaianolevine/deejay-marvel-api/commit/3175cd6c506b61091e613eecdf93b538876c1d96))

# Changelog

## [0.3.1] - 2026-03-19
### Added
- track_count to SetListItem and SetDetail responses

## [0.3.0] - 2026-03-19
### Added
- CI workflow (lint + test on every push and PR)
- feature_flags table with three initial flags seeded
- GET /v1/flags and PATCH /v1/flags/{name} endpoints
- Flag check on ingest endpoint via is_enabled() service

## [0.2.0] - 2026-03-19
### Added
- Expanded pipeline_evaluations table with structured fields
  (run_id, finding, suggestion, standards_version, evaluated_at)
- POST /v1/evaluations accepts structured PipelineEvaluationCreate
- GET /v1/evaluations and GET /v1/evaluations/summary endpoints

## [0.1.6] - 2026-03-19
### Added
- CORSMiddleware configurable via CORS_ORIGINS environment variable

## [0.1.5] - 2026-03-19
### Added
- track_count field on SetListItem and SetDetail responses

## [0.1.3] - 2026-03-18
### Changed
- Redefined data_quality to use 4 enrichment fields only
  (genre, length_secs, bpm, release_year)

## [0.1.2] - 2026-03-18
### Added
- Historical data migration script (now removed — replaced by
  POST /v1/admin/migrate endpoint pattern)

## [0.1.1] - 2026-03-18
### Added
- Missing CSV columns: remix, label, comment
- Fixed play_order nullability

## [0.1.0] - 2026-03-18
### Added
- Initial implementation. FastAPI service with PostgreSQL via
  SQLAlchemy async. Five tables: sets, tracks, track_catalog,
  pipeline_evaluations, feature_flags. All endpoints implemented.
  Reconciliation and normalization services. Contract tests for
  all endpoints.
