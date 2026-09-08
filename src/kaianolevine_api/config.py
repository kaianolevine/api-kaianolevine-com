from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    DATABASE_URL: str

    # OPS-002. The connection the migration step uses, bound to a role that
    # owns the schema. Declared here so the two roles are visible in one
    # place, but deliberately never read by anything under src/: the whole
    # point is that the DDL-capable role is unreachable from the request
    # path. scripts/apply_migrations.py reads the environment variable
    # directly, and that script runs before uvicorn in the start command.
    #
    # Optional, and the migration runner falls back to DATABASE_URL when it
    # is unset, so the separation can be turned on by provisioning the role
    # and setting the variable rather than by a deploy that fails until
    # both happen at once.
    DATABASE_URL_MIGRATIONS: str | None = None

    ENVIRONMENT: str = "development"
    API_VERSION: str = "1.0"
    STANDARDS_VERSION: str = "3.4.2"
    SENTRY_DSN_API: str | None = None
    CORS_ORIGINS: list[str] = ["*"]

    # Logging
    LOGGING_LEVEL: str = "INFO"

    # HTTP client timeouts — override to 0 in tests for fast failure
    HTTP_CLIENT_TIMEOUT_SECS: float = 10.0

    # Clerk JWT (Project Keystone) — required when flags.keystone.clerk_auth_enabled is TRUE
    CLERK_JWKS_URL: str | None = None
    CLERK_ISSUER: str | None = None

    # Multi-issuer form, used by the identity binding. JSON array of
    # {issuer, jwks_url}. When unset, the two singular vars above are read
    # as the one-tenant shorthand. The two Clerk tenants are separate
    # products and are never merged into one issuer. No secret key: machines
    # hold their own named API keys and never authenticate through Clerk.
    CLERK_ISSUERS: str | None = None

    # Contact form
    BREVO_API_KEY: str | None = None
    CONTACT_TO_EMAIL: str | None = None
    CONTACT_FROM_EMAIL: str | None = None
    TURNSTILE_SECRET_KEY: str | None = None

    # Discord notifications (GitHub CI failures + the /notify route).
    # One webhook URL for both: services.discord appends Discord's /github
    # suffix for GitHub-shaped payloads and posts to the bare URL otherwise,
    # so a value pasted with the suffix already on it still works.
    DISCORD_WEBHOOK_URL: str | None = None
    # Shared secret configured on the GitHub org webhook. Unset means the
    # route rejects every delivery rather than accepting unsigned ones.
    GITHUB_WEBHOOK_SECRET: str | None = None
    # Which GitHub events may reach Discord. One failing Actions run emits
    # check_run (per job), check_suite and workflow_run for the same failure;
    # forwarding all three posts the same news three times. workflow_run is
    # the run-level summary and status covers non-Actions checks, so the two
    # of them report every failure exactly once. Widen it here — not in the
    # route — if a check that reports through check_run only ever appears.
    GITHUB_NOTIFY_EVENTS: list[str] = ["workflow_run", "status"]

    # Google service account (Drive resume proxy)
    GOOGLE_CLIENT_EMAIL: str | None = None
    GOOGLE_PRIVATE_KEY: str | None = None  # PEM with literal \n — see validator
    RESUME_FILE_ID: str | None = None

    # WCS Q&A retrieval / agent
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    WCS_QA_EMBEDDING_MODEL: str = "text-embedding-3-small"
    WCS_QA_FLATTENER_VERSION: int = 1
    WCS_QA_CHUNKING_VERSION: int = 1
    WCS_QA_AGENT_MODEL: str = "claude-sonnet-4-6"
    WCS_QA_JUDGE_MODEL: str = "claude-opus-4-7"
    # Per-request agent budgets. Two layers:
    #   _DEFAULT — what every request gets.
    #   _LIMIT   — hard ceiling clamped against the default (and against any
    #              future per-request override); a request can never exceed
    #              this regardless of input.
    # Defaults are sized for synthesis-heavy questions ("top N across all
    # lessons") since the agent is admin-only today. If you ever open this
    # to general users, drop the defaults and re-introduce a tiered override
    # path (see git history before this change for the depth/preset scaffold).
    WCS_QA_MAX_TOOL_CALLS_DEFAULT: int = 25
    WCS_QA_MAX_TOOL_CALLS_LIMIT: int = 30
    WCS_QA_MAX_INPUT_TOKENS_DEFAULT: int = 160_000
    WCS_QA_MAX_INPUT_TOKENS_LIMIT: int = 200_000
    WCS_QA_MAX_OUTPUT_TOKENS_DEFAULT: int = 8000
    WCS_QA_MAX_OUTPUT_TOKENS_LIMIT: int = 8192
    WCS_SITE_URL: str = "https://wcs.kaianolevine.com"

    @field_validator("GOOGLE_PRIVATE_KEY", mode="before")
    @classmethod
    def normalize_google_private_key_newlines(cls, v: str | None) -> str | None:
        """Normalize escaped newlines in GOOGLE_PRIVATE_KEY values."""
        if v is None or v == "":
            return v
        return v.replace("\\n", "\n")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings instance for this process."""
    return Settings()
