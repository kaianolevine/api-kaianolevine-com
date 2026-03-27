# [1.10.0](https://github.com/kaianolevine/api-kaianolevine-com/compare/v1.9.0...v1.10.0) (2026-03-27)


### Features

* reverting auth ([e464cee](https://github.com/kaianolevine/api-kaianolevine-com/commit/e464cee0a7793b2e6c421a5e8614671eb95457e4))

# [1.9.0](https://github.com/kaianolevine/api-kaianolevine-com/compare/v1.8.0...v1.9.0) (2026-03-27)


### Features

* pre commit cleanup ([1e84439](https://github.com/kaianolevine/api-kaianolevine-com/commit/1e844394f1b70a82823ddeebac086b82187d8dbb))

# [1.8.0](https://github.com/kaianolevine/api-kaianolevine-com/compare/v1.7.0...v1.8.0) (2026-03-27)


### Features

* adding clerk functionality ([3ad8a68](https://github.com/kaianolevine/api-kaianolevine-com/commit/3ad8a68442577ef9f7d44164377b3c25ff191b5c))

# [1.7.0](https://github.com/kaianolevine/api-kaianolevine-com/compare/v1.6.1...v1.7.0) (2026-03-26)


### Features

* adding resume endpoint to api from legacy api ([77f160c](https://github.com/kaianolevine/api-kaianolevine-com/commit/77f160cbff15fc52ec541450c0af6f61f25e5efd))

## [1.6.1](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.6.0...v1.6.1) (2026-03-26)


### Bug Fixes

* contact ([4f87db5](https://github.com/kaianolevine/deejay-marvel-api/commit/4f87db5f83a8f0e3058a2bf86ccf12ada4117e64))

# [1.6.0](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.5.1...v1.6.0) (2026-03-26)


### Features

* migrating legacy api contact to this api for final migration of legacy functionality ([f9568db](https://github.com/kaianolevine/deejay-marvel-api/commit/f9568db6099f6f481b9886e6bf98f447de2138f8))

## [1.5.1](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.5.0...v1.5.1) (2026-03-24)


### Bug Fixes

* adding duplicate detection at the api layer ([f8a54e6](https://github.com/kaianolevine/deejay-marvel-api/commit/f8a54e682e23531f9b7cc333833a861f7c1ff076))

# [1.5.0](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.4.0...v1.5.0) (2026-03-23)


### Features

* adding flow name information ([e29fee7](https://github.com/kaianolevine/deejay-marvel-api/commit/e29fee71e5d0cd6607d1c1d69ca175e5a274c5ee))

# [1.4.0](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.3.0...v1.4.0) (2026-03-23)


### Features

* migration + schema + both routers (evaluations and webhook) ([72f63d9](https://github.com/kaianolevine/deejay-marvel-api/commit/72f63d971633e5e2dd67a09a3d619891e86e4be4))

# [1.3.0](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.2.1...v1.3.0) (2026-03-23)


### Features

* Adding webhook endpoints for prefect ([41d05bb](https://github.com/kaianolevine/deejay-marvel-api/commit/41d05bbad64c0e1ee68ccfd4bba52179bd0e234b))

## [1.2.1](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.2.0...v1.2.1) (2026-03-23)


### Bug Fixes

* use pg_insert unconditionally in live plays router ([1455f73](https://github.com/kaianolevine/deejay-marvel-api/commit/1455f7324c3f6464b71b92e93f69e0ef9819abad))

# [1.2.0](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.1.0...v1.2.0) (2026-03-23)


### Features

* fix inner joins to handle nullable set_id for orphaned live tracks ([8e8f093](https://github.com/kaianolevine/deejay-marvel-api/commit/8e8f0935abf8fe64fbc3c76d4f838e774b1f7f8d))

# [1.1.0](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.0.0...v1.1.0) (2026-03-23)


### Features

* add live play history ingest and recent plays endpoint ([3879193](https://github.com/kaianolevine/deejay-marvel-api/commit/3879193b086327b5b657d1601d08efb6f04cd697))

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
