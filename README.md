# kaianolevine-api

FastAPI service powering api.kaianolevine.com — sets, tracks, catalog
reconciliation, pipeline evaluations, feature flags, stats, live plays,
contact form handling (Brevo + Turnstile), and resume PDF proxy
(Google Drive).

## Developer Setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
- PostgreSQL (or use the `DATABASE_URL` from Railway for a shared dev DB)

### First-time setup
```bash
# 1. Install all dependencies including dev extras
uv sync --all-extras

# 2. Install pre-commit hooks
uv run pre-commit install

# 3. Copy env file and fill in values
cp .env.example .env
```

### Run the server
```bash
uv run uvicorn src.kaianolevine_api.main:app --reload
```

API docs available at http://localhost:8000/docs

### Run tests
```bash
# All tests (uses SQLite in-memory — no DATABASE_URL needed)
uv run pytest

# With coverage detail
uv run pytest --cov=src --cov-report=term-missing
```

### Lint, format, type check
```bash
uv run ruff check src/ tests/ --fix
uv run ruff format src/ tests/
uv run mypy src/
```

### Pre-commit (runs automatically on every commit)
```bash
# Run manually against all files
uv run pre-commit run --all-files
```

Hooks run on every `git commit`: ruff lint, ruff format, mock method checks, type annotation checks. If a hook fails the commit is blocked — ruff will auto-fix in place, then `git add .` and re-commit.

## CI/CD

Every push to `main` runs CI (lint + tests).
Railway auto-deploys on push to `main`.
Feature flags control activation without deployment.
Flags are managed via `PATCH /v1/flags/{name}`.

## Versioning

This repo uses semantic-release for automated versioning.
Versions are determined automatically from commit messages
on merge to main:

- feat: → minor version bump (0.3.1 → 0.4.0)
- fix: → patch version bump (0.3.1 → 0.3.2)
- feat!: or BREAKING CHANGE → major bump (0.3.1 → 1.0.0)
- chore/docs/refactor/test/ci → no version bump

Never manually edit the version in pyproject.toml.
Never manually edit CHANGELOG.md.
Both are managed automatically on merge to main.

### Production Flag Rollback

Use flags for safe rollout and fast rollback without redeploying:

- Enable one flag change at a time via `PATCH /v1/flags/{name}`.
- Verify health immediately after change (API status, error logs, and endpoint behavior).
- If regressions appear, rollback by patching the same flag back to `enabled: false` (or `true` for previously disabled flags).
- Prefer changing ingest-related flags during low-traffic windows and monitor pipeline runs for 5-10 minutes after each change.
- Record each production flag flip in deployment notes (flag name, old/new value, timestamp, operator).

## Deployment Target

Designed for Railway.

## Authentication

Owner-based auth is implemented for now via a placeholder `get_current_owner` dependency.
Clerk JWT verification is planned for production.
