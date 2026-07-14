"""Analyses API: create (multipart), list, get, delete, and error branches."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from tests.conftest import SAMPLE_DIR, sample_files, sample_form


def test_create_analysis_ok(client: TestClient) -> None:
    resp = client.post("/api/analyses", data=sample_form(), files=sample_files())
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "needs_review"
    assert body["spot_count"] == 4  # notes_sample.csv has four rows
    assert body["chamber_area_m2"] == 0.0625
    assert body["id"]

    # Raw files were stored on disk under data/<id>/.
    analysis_dir = Path(settings.data_dir) / body["id"]
    assert (analysis_dir / "concentration.txt").exists()
    assert (analysis_dir / "notes.csv").exists()


def test_missing_file_returns_422_naming_it(client: TestClient) -> None:
    files = sample_files()
    del files["pressure"]
    resp = client.post("/api/analyses", data=sample_form(), files=files)
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "missing_file"
    assert resp.json()["detail"]["field"] == "pressure"


def test_bad_li7810_returns_422(client: TestClient) -> None:
    # Send the temperature xlsx in the concentration slot -> not a LI-7810 file.
    files = sample_files()
    files["concentration"] = (
        "temperature_sample.xlsx",
        (SAMPLE_DIR / "temperature_sample.xlsx").read_bytes(),
        "application/octet-stream",
    )
    resp = client.post("/api/analyses", data=sample_form(), files=files)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "bad_li7810"
    assert detail["field"] == "concentration"
    assert "SECONDS" in detail["message"]


def test_duplicate_name_returns_409(client: TestClient) -> None:
    client.post("/api/analyses", data=sample_form(name="Dup"), files=sample_files())
    resp = client.post(
        "/api/analyses", data=sample_form(name="Dup"), files=sample_files()
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "duplicate_name"
    assert detail["field"] == "name"


def test_list_is_newest_first(client: TestClient) -> None:
    client.post("/api/analyses", data=sample_form(name="First"), files=sample_files())
    client.post("/api/analyses", data=sample_form(name="Second"), files=sample_files())
    resp = client.get("/api/analyses")
    assert resp.status_code == 200
    names = [a["name"] for a in resp.json()]
    assert names == ["Second", "First"]
    assert all("spot_count" in a for a in resp.json())


def test_get_one_and_404(client: TestClient) -> None:
    created = client.post(
        "/api/analyses", data=sample_form(), files=sample_files()
    ).json()
    resp = client.get(f"/api/analyses/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["chamber_volume_l"] == 15.625

    missing = client.get("/api/analyses/nope")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "not_found"


def test_oversized_file_returns_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Shrink the cap so the small sample files trip it (avoids a 50 MB fixture).
    monkeypatch.setattr("app.api.analyses.MAX_UPLOAD_BYTES", 10)
    resp = client.post("/api/analyses", data=sample_form(), files=sample_files())
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "file_too_large"


def test_delete_removes_analysis_and_files(client: TestClient) -> None:
    created = client.post(
        "/api/analyses", data=sample_form(), files=sample_files()
    ).json()
    analysis_dir = Path(settings.data_dir) / created["id"]
    assert analysis_dir.exists()

    resp = client.delete(f"/api/analyses/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/analyses/{created['id']}").status_code == 404
    assert not analysis_dir.exists()
