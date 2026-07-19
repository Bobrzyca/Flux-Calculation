"""Parsed-notes API: GET flags, PUT confirmed rows, add/delete round-trip."""

from fastapi.testclient import TestClient

from tests.conftest import sample_files, sample_form


def _create(client: TestClient) -> str:
    resp = client.post("/api/analyses", data=sample_form(), files=sample_files())
    return str(resp.json()["id"])


def test_get_notes_has_flags(client: TestClient) -> None:
    analysis_id = _create(client)
    resp = client.get(f"/api/analyses/{analysis_id}/notes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["parse_failed"] is False
    by_nr = {r["nr"]: r for r in body["rows"]}
    assert by_nr[1]["flags"] == []  # clean row
    assert "gps_missing" in by_nr[2]["flags"]  # blank GPS
    assert "stop_before_start" in by_nr[4]["flags"]  # 09:30 -> 09:25


def test_put_notes_clears_flag_and_persists(client: TestClient) -> None:
    analysis_id = _create(client)
    rows = client.get(f"/api/analyses/{analysis_id}/notes").json()["rows"]
    # Fix row 4's stop time so it no longer precedes the start.
    for row in rows:
        if row["nr"] == 4:
            row["stop_time"] = "09:36:00"

    resp = client.put(f"/api/analyses/{analysis_id}/notes", json=rows)
    assert resp.status_code == 200
    by_nr = {r["nr"]: r for r in resp.json()["rows"]}
    assert "stop_before_start" not in by_nr[4]["flags"]

    # Persisted: a fresh GET reflects the fix.
    again = client.get(f"/api/analyses/{analysis_id}/notes").json()
    assert "stop_before_start" not in {
        f for r in again["rows"] if r["nr"] == 4 for f in r["flags"]
    }


def test_put_notes_add_and_delete_rows(client: TestClient) -> None:
    analysis_id = _create(client)
    rows = client.get(f"/api/analyses/{analysis_id}/notes").json()["rows"]
    # Drop row 3, add a new row 5.
    rows = [r for r in rows if r["nr"] != 3]
    rows.append(
        {
            "nr": 5,
            "start_time": "11:00:00",
            "stop_time": "11:06:00",
            "gps": "52.4,20.6",
            "light_dark": "light",
            "location": "new plot",
            "flags": [],
        }
    )
    resp = client.put(f"/api/analyses/{analysis_id}/notes", json=rows)
    assert resp.status_code == 200
    nrs = sorted(r["nr"] for r in resp.json()["rows"])
    assert nrs == [1, 2, 4, 5]

    # And the analysis's spot_count reflects the new set.
    summary = client.get(f"/api/analyses/{analysis_id}").json()
    assert summary["spot_count"] == 4


def test_put_notes_normalizes_times(client: TestClient) -> None:
    # Hand-edited times without seconds (or with dots) must be stored as
    # HH:MM:SS — "10:35" strings previously crashed the match step.
    analysis_id = _create(client)
    rows = client.get(f"/api/analyses/{analysis_id}/notes").json()["rows"]
    for row in rows:
        if row["nr"] == 1:
            row["start_time"] = "9:41"
            row["stop_time"] = "09.47"

    resp = client.put(f"/api/analyses/{analysis_id}/notes", json=rows)
    assert resp.status_code == 200
    by_nr = {r["nr"]: r for r in resp.json()["rows"]}
    assert by_nr[1]["start_time"] == "09:41:00"
    assert by_nr[1]["stop_time"] == "09:47:00"


def test_notes_unknown_analysis_404(client: TestClient) -> None:
    assert client.get("/api/analyses/nope/notes").status_code == 404
    assert client.put("/api/analyses/nope/notes", json=[]).status_code == 404
