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

    # --- Flux / parsing thresholds ----------------------------------------
    # Upper plausibility bound for CO₂ (ppm): readings at or above this are
    # treated as sensor artefacts and dropped before fitting. Configurable
    # because high-flux substrates (manure, very active soils) can genuinely
    # exceed the old 1500 ppm bound over a closure. Override via
    # MAX_VALID_CO2_PPM in the environment / .env.
    max_valid_co2_ppm: float = 5000.0

    # --- Logging -----------------------------------------------------------
    # Minimum level emitted: DEBUG | INFO | WARNING | ERROR | CRITICAL.
    log_level: str = "INFO"
    # Output format: "json" (production, machine-readable) or "console"
    # (compact, human-friendly for local development).
    log_format: str = "json"
    # Requests slower than this (milliseconds) are logged as a `slow_request`
    # warning in addition to the normal completion line.
    slow_request_ms: int = 1000

    # --- Monitoring (Sentry) ----------------------------------------------
    # Error/performance monitoring is OFF unless a DSN is set — the app must
    # start and run fully without it. The DSN is not a secret (it ships in the
    # frontend bundle too), but is kept in .env with the other config.
    sentry_dsn: str | None = None
    # Logical environment tag on every event (e.g. production | staging | dev).
    sentry_environment: str = "development"
    # Release identifier — set from the git commit SHA at build/run time so
    # regressions can be tied to a deploy. Blank → SDK falls back to git in dev.
    sentry_release: str | None = None
    # Fraction of requests traced for performance (0.0 = off; keep low on the
    # Sentry free tier). 0.0–1.0.
    sentry_traces_sample_rate: float = 0.0

    # Placeholder — the LLM field-notes/pressure parser is seminar 6.
    # TODO: LLM API key wiring (seminar 6).
    llm_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed once per process."""
    return Settings()


settings = get_settings()
