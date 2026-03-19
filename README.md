# deejay-sets-api

FastAPI service providing:
* CRUD-style read endpoints for `sets` and `tracks`
* A `track_catalog` for normalized track matching + reconciliation
* Pipeline evaluation endpoints (list, summary, and write)
* Basic usage statistics endpoints
* An ingest endpoint that runs reconciliation and catalog upsert logic

## Local Development

### Prerequisites

* Python 3.11+
* `uv` installed

### Environment

Copy `.env.example` to `.env` and adjust values as needed.
In production, set `CORS_ORIGINS` to the specific Cloudflare Pages domain(s) rather than using the wildcard (`*`).

## Run the Server

API docs are available at `http://localhost:8000/docs`.

```bash
uv run uvicorn src.deejay_sets_api.main:app --reload
```

## Run Tests

```bash
uv run pytest --cov=src --cov-report=term-missing
```

## Deployment Target

Designed for Railway.

## Authentication

Owner-based auth is implemented for now via a placeholder `get_current_owner` dependency.
Clerk JWT verification is planned for production.

## Historical Data Migration

One-time script to import all historical DJ set data from Google Sheets into PostgreSQL.

Prerequisites:
- `DATABASE_URL` set in `.env` pointing to your PostgreSQL instance
- `GOOGLE_CREDENTIALS_JSON` set in `.env` with service account credentials

Test run (one year only):
```bash
uv run python scripts/migrate_historical_data.py \
  --collection path/to/deejay_set_collection.json \
  --year 2026
```

Full migration:
```bash
uv run python scripts/migrate_historical_data.py \
  --collection path/to/deejay_set_collection.json
```

After running, check `scripts/migration_report.txt` to verify counts.

