"""Application configuration.

All runtime configuration is centralized here and sourced from environment
variables (12-factor style), so the same image runs unchanged across local,
staging, and production. A `.env` file is loaded for local convenience.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Storage -----------------------------------------------------------
    # SQLite by default for zero-config local dev; point at Postgres in prod
    # by setting DATABASE_URL=postgresql+psycopg://user:pass@host/db
    database_url: str = "sqlite:///./cosailor.db"

    # --- Target market -----------------------------------------------------
    target_zip: str = "10013"
    search_radius_miles: int = 25

    # --- GAF data source (Coveo Search API) --------------------------------
    # GAF's public contractor directory is powered by Coveo. These are the
    # client-side (search-only) credentials GAF ships in the page HTML to every
    # visitor, so they are not secrets; kept here as env-overridable config in
    # case GAF rotates them.
    coveo_org: str = "gafmaterialscorporationproduction3yalqk12"
    coveo_api_key: str = "xx3cfe6ca4-11f2-45b6-83ad-41e053e06504"
    coveo_pipeline: str = "prod-gaf-recommended-residential-contractors"
    # Cap leads ingested per run so a demo/live run is bounded in time + AI
    # spend. Production would page through all results into the queue.
    scrape_max_results: int = 60

    # --- AI providers ------------------------------------------------------
    openai_api_key: str | None = None
    perplexity_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    perplexity_model: str = "sonar"

    # --- Pipeline tuning (scale knobs) ------------------------------------
    # Bounded concurrency keeps us within provider rate limits while still
    # processing many leads in parallel. Raise as quota allows.
    enrich_concurrency: int = 5
    enrich_max_attempts: int = 3
    enrich_backoff_base_seconds: float = 2.0
    http_timeout_seconds: float = 30.0

    # --- Behaviour ---------------------------------------------------------
    # When true (or when keys are absent) the pipeline runs entirely offline
    # using deterministic stub enrichment + seed contractors. This lets the
    # full app be demoed without network access or spend.
    mock_mode: bool = False

    @property
    def effective_mock_mode(self) -> bool:
        """Fall back to mock mode automatically when no AI keys are set."""
        if self.mock_mode:
            return True
        return not (self.openai_api_key and self.perplexity_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
