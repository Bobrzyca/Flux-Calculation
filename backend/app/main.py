"""FastAPI entry point and route wiring.

Routes are served under the ``/api`` prefix (the frontend calls
``/api/analyses`` etc.). For now only the health check exists; feature routers
are added in later chunks.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyses, export, match, notes, results
from app.core.config import settings
from app.db.session import create_db_and_tables


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks: ensure the data dir exists and tables are created."""
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    create_db_and_tables()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

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
