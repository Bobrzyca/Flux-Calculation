"""Application settings, loaded from the environment / `.env`.

Everything configurable lives here so the rest of the app reads a single
`settings` object. Values can be overridden by environment variables (matching
the field name, case-insensitive) or a local `.env` file.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Flux Calculation API"

    # Where uploaded files and the SQLite database live (created on startup).
    data_dir: str = "./data"
    database_url: str = "sqlite:///./data/flux.db"

    # Origins allowed by CORS — the Vite dev server by default.
    cors_origins: list[str] = ["http://localhost:5173"]

    # Placeholder — the LLM field-notes/pressure parser is seminar 6.
    # TODO: LLM API key wiring (seminar 6).
    llm_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed once per process."""
    return Settings()


settings = get_settings()
