"""Central configuration. candidate_id is defined here ONCE and normalised.

Everything else in the codebase imports CANDIDATE_ID from here — it is never
re-typed as a literal. See §0.1 of the brief.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_candidate_id(value: str) -> str:
    """Lowercase + trim. Applied on every write and read of candidate_id."""
    return (value or "").strip().lower()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    candidate_id: str = "manviitnd0408@gmail.com"
    database_url: str = "sqlite:///./dev.db"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_max_concurrency: int = 5
    gemini_max_retries: int = 3

    # Optional Groq provider (OpenAI-compatible, free tier). If set, it takes
    # priority over Gemini. Get a key at console.groq.com.
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    cors_origins: str = "http://localhost:5173"

    @property
    def CANDIDATE_ID(self) -> str:  # noqa: N802 - deliberately shouty
        return normalize_candidate_id(self.candidate_id)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        """Normalise common Postgres URL variants to the psycopg v3 driver."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.sqlalchemy_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
CANDIDATE_ID = settings.CANDIDATE_ID
