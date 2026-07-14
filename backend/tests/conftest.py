"""Shared API-test fixtures: a TestClient on a throwaway DB + temp data dir.

Each test gets a fresh in-memory SQLite engine (StaticPool so it survives across
sessions) and a temp ``data/`` directory, so nothing touches the real database or
repo files. ``get_session`` is overridden to use the test engine. We deliberately
do NOT enter the app's lifespan (no ``with TestClient``), so startup doesn't build
the real on-disk DB.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.db.session import get_session
from app.main import app

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _session_override() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _session_override
    yield TestClient(app)
    app.dependency_overrides.clear()


def sample_files(
    concentration: str = "li7810_sample.txt",
) -> dict[str, tuple[str, bytes, str]]:
    """Multipart ``files=`` mapping using the committed sample fixtures."""
    return {
        "concentration": (
            "li7810_sample.txt",
            (SAMPLE_DIR / concentration).read_bytes(),
            "text/plain",
        ),
        "notes": (
            "notes_sample.csv",
            (SAMPLE_DIR / "notes_sample.csv").read_bytes(),
            "text/csv",
        ),
        "temperature": (
            "temperature_sample.xlsx",
            (SAMPLE_DIR / "temperature_sample.xlsx").read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        "pressure": (
            "pressure_sample.csv",
            (SAMPLE_DIR / "pressure_sample.csv").read_bytes(),
            "text/csv",
        ),
    }


def sample_form(name: str = "Kampinos 2 July", offset: str = "0") -> dict[str, str]:
    return {
        "name": name,
        "work_date": "2026-07-02",
        "chamber_area_m2": "0.0625",
        "chamber_volume_l": "15.625",
        "time_offset_seconds": offset,
    }
