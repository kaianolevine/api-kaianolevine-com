# Changelog

## Version 0.1.0

- Date: 2026-03-18
- Entry: "Initial implementation. FastAPI service with PostgreSQL via SQLAlchemy async. Five tables: sets, tracks, track_catalog, pipeline_evaluations. All endpoints from design document implemented. Reconciliation and normalization services. Contract tests for all endpoints."

## Version 0.1.1

- Date: 2026-03-18
- Entry: "Added missing CSV columns (remix, label, comment) to tracks and catalog tables. Fixed play_order nullability. Added .env.example. Added TODO note for Phase 3 pipeline_evaluations expansion."

## Version 0.1.2

- Date: 2026-03-18
- Entry: "Added historical data migration script with idempotency,
  per-year verification report, and spot check against expected counts."

## Version 0.1.3
- Date: 2026-03-18
- Entry: "Redefined data_quality to use 4 enrichment fields (genre, length_secs, bpm, release_year) instead of 8. play_time and play_order are operational fields, not data quality signals."

