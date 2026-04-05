from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    ENVIRONMENT: str = "development"
    API_VERSION: str = "1.0"
    OWNER_ID: str = "dev-owner"
    SENTRY_DSN_API: str | None = None
    CORS_ORIGINS: list[str] = ["*"]

    # Contact form
    BREVO_API_KEY: str | None = None
    CONTACT_TO_EMAIL: str | None = None
    CONTACT_FROM_EMAIL: str | None = None
    TURNSTILE_SECRET_KEY: str | None = None

    # Google service account (Drive resume proxy)
    GOOGLE_CLIENT_EMAIL: str | None = None
    GOOGLE_PRIVATE_KEY: str | None = None  # PEM with literal \n — see validator
    RESUME_FILE_ID: str | None = None

    @field_validator("GOOGLE_PRIVATE_KEY", mode="before")
    @classmethod
    def normalize_google_private_key_newlines(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        return v.replace("\\n", "\n")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
