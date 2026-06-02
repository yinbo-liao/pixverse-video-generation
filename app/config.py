"""Application configuration loaded from environment / .env file.

Uses pydantic-settings for automatic .env loading and validation.
The get_settings() function is cached with lru_cache so the .env
file is read only once per process.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """PixVerse Bridge configuration.

    All values can be overridden via environment variables or a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Semantic-Canvas upstream ---
    semantic_canvas_base_url: str = "http://localhost:8000"
    semantic_canvas_api_key: str | None = None
    semantic_canvas_timeout: int = 30
    semantic_canvas_mock: bool = False  # If True, use MockSemanticCanvasClient (no upstream needed)

    # --- PixVerse V6 (placeholder for Phase 2+) ---
    pixverse_api_key: str | None = None

    # --- Application ---
    log_level: str = "INFO"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    Using lru_cache ensures .env is parsed once. Tests that need
    different settings should use FastAPI dependency_overrides rather
    than attempting to mutate the cached instance.
    """
    return Settings()
