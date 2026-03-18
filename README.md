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

