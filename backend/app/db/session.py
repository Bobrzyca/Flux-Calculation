"""Database engine, session dependency, and table creation.

The engine is built once from ``settings.database_url`` (SQLite by default). Use
``get_session`` as a FastAPI dependency to obtain a scoped ``Session`` per
request, and ``create_db_and_tables`` on startup to create any missing tables.
"""

from collections.abc import Iterator

from sqlalchemy import text
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
    _run_lightweight_migrations()


def _run_lightweight_migrations() -> None:
    """Add columns introduced after a DB was first created.

    ``create_all`` never alters an existing table, so a column added to a model
    later (e.g. ``Spot.manual_offset_s``) is missing from an already-deployed
    SQLite file. We add such columns idempotently with ``ADD COLUMN`` (a no-op
    when they already exist). Kept tiny on purpose — a full migration tool
    (Alembic) is overkill for this single-file, single-user DB.
    """
    if not settings.database_url.startswith("sqlite"):
        return
    _add_column_if_missing("spot", "manual_offset_s", "FLOAT")


def _add_column_if_missing(table: str, column: str, sql_type: str) -> None:
    with engine.begin() as conn:
        cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
        if column not in cols:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yield a session, closing it after the request."""
    with Session(engine) as session:
        yield session
