"""Raw-file storage: uploaded files land under data/<analysis_id>/<role>.<ext>."""

from pathlib import Path

import pytest

from app.core.config import settings
from app.db import storage


def test_save_and_read_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    content = b"DATA\nSECONDS\tCO2\tCH4\n1751442000\t412.5\t1975\n"

    path = storage.save_upload(
        "analysis123", "concentration", "LI7810_export.txt", content
    )

    assert path == tmp_path / "analysis123" / "concentration.txt"
    assert path.read_bytes() == content  # byte-identical on disk
    assert storage.read_stored(path) == content
    assert storage.find_stored("analysis123", "concentration") == path


def test_extension_is_preserved_per_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))

    notes = storage.save_upload("a1", "notes", "field notes.docx", b"x")
    temp = storage.save_upload("a1", "temperature", "temps.xlsx", b"y")

    assert notes.name == "notes.docx"
    assert temp.name == "temperature.xlsx"
    # Both roles live under the same per-analysis directory.
    assert notes.parent == temp.parent == tmp_path / "a1"


def test_rejects_unknown_role(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    with pytest.raises(ValueError):
        storage.save_upload("a1", "bogus", "x.txt", b"x")


def test_find_stored_missing_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    assert storage.find_stored("nope", "pressure") is None
