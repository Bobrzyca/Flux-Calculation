"""FastAPI entry point and route wiring.

Routes are served under the ``/api`` prefix (the frontend calls
``/api/analyses`` etc.). For now only the health check exists; feature routers
are added in later chunks.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyses, export, match, notes, results
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.core.monitoring import configure_monitoring
from app.db.session import create_db_and_tables

# Configure logging as early as possible so import-time and startup logs are
# already structured.
configure_logging(level=settings.log_level, fmt=settings.log_format)
log = get_logger("app.main")

# Initialise error/performance monitoring before the app is built so the Sentry
# integrations can hook FastAPI. A no-op when SENTRY_DSN is unset.
monitoring_enabled = configure_monitoring(
    dsn=settings.sentry_dsn,
    environment=settings.sentry_environment,
    release=settings.sentry_release,
    traces_sample_rate=settings.sentry_traces_sample_rate,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks: ensure the data dir exists and tables are created."""
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    create_db_and_tables()
    # Log the (non-secret) effective configuration on startup. Secrets such as
    # LLM_API_KEY are deliberately never logged — only whether one is set.
    log.info(
        "app.startup",
        extra={
            "app_name": settings.app_name,
            "data_dir": settings.data_dir,
            "log_level": settings.log_level,
            "log_format": settings.log_format,
            "slow_request_ms": settings.slow_request_ms,
            "cors_origins": settings.cors_origins,
            # Whether an LLM key is set — never the key itself. (Field name
            # deliberately avoids "api_key" so the boolean isn't redacted.)
            "llm_configured": bool(settings.llm_api_key),
            "monitoring_enabled": monitoring_enabled,
            "sentry_environment": settings.sentry_environment,
        },
    )
    yield
    log.info("app.shutdown")


try:
    _API_VERSION = version("flux-calculation-backend")
except PackageNotFoundError:  # running from a source tree without an install
    _API_VERSION = "0.0.0+local"

# Description shows at the top of the generated OpenAPI docs (docs/openapi.json).
# Keep it accurate to the code: local single-user tool, all routes under /api.
_API_DESCRIPTION = (
    "HTTP API for the Flux Calculation tool — ingests raw closed-chamber "
    "greenhouse-gas field files, matches them by timestamp, fits a per-spot "
    "linear regression, and computes CO₂/CH₄ flux across a unit ladder.\n\n"
    "All routes are served under the `/api` prefix. The app is **local and "
    "single-user**: there is no authentication and every endpoint is on the same "
    "trust level (see `docs/architecture.md`)."
)

app = FastAPI(
    title=settings.app_name,
    version=_API_VERSION,
    description=_API_DESCRIPTION,
    # Relative server: paths already carry the /api prefix, so this resolves
    # against whatever host serves the app (localhost in dev, the domain in prod).
    servers=[{"url": "/", "description": "Same origin the app is served from"}],
    lifespan=lifespan,
)

# Correlation id + per-request logging. Added before CORS so it is the
# outermost app middleware and sees every request/response (incl. its id echo).
app.add_middleware(RequestContextMiddleware, slow_request_ms=settings.slow_request_ms)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe used by tests and ops."""
    return {"status": "ok", "app": settings.app_name}


app.include_router(analyses.router)
app.include_router(notes.router)
app.include_router(match.router)
app.include_router(results.router)
app.include_router(export.router)
