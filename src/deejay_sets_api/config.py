from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    ENVIRONMENT: str = "development"
    API_VERSION: str = "1.0"
    OWNER_ID: str = "dev-owner"
    SENTRY_DSN: str | None = None
    CORS_ORIGINS: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_current_owner(settings: Settings = Depends(get_settings)) -> str:
    """
    Placeholder owner resolution for now.

    TODO: Replace with Clerk JWT verification before going to production.
    """

    return settings.OWNER_ID
