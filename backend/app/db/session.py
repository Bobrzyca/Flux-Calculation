"""Database engine, session dependency, and table creation.

The engine is built once from ``settings.database_url`` (SQLite by default). Use
``get_session`` as a FastAPI dependency to obtain a scoped ``Session`` per
request, and ``create_db_and_tables`` on startup to create any missing tables.
"""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# Import the models module so every table registers on ``SQLModel.metadata``
# before ``create_all`` runs.
from app.db import models  # noqa: F401

# SQLite + a threaded server (uvicorn/TestClient) needs check_same_thread off.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)


def create_db_and_tables() -> None:
    """Create all tables that don't yet exist. Safe to call repeatedly."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yield a session, closing it after the request."""
    with Session(engine) as session:
        yield session
