"""Read endpoints: results table, per-spot detail, processing log."""

from fastapi.testclient import TestClient

from tests.conftest import sample_files, sample_form


def _create_and_match(client: TestClient) -> str:
    analysis_id = str(
        client.post("/api/analyses", data=sample_form(), files=sample_files()).json()[
            "id"
        ]
    )
    client.post(f"/api/analyses/{analysis_id}/match")
    return analysis_id


def test_results_payload(client: TestClient) -> None:
    analysis_id = _create_and_match(client)
    resp = client.get(f"/api/analyses/{analysis_id}/results")
    assert resp.status_code == 200
    payload = resp.json()

    # n8n quality check is deferred.
    assert payload["quality_check"]["available"] is False
    assert payload["quality_check"]["flags"] == []

    by_nr = {s["nr"]: s for s in payload["spots"]}
    assert len(by_nr) == 4

    # Spot 1: clean fit, some nan dropped in-window.
    assert by_nr[1]["skipped"] is False
    assert by_nr[1]["co2_flux_umol_m2_s"] is not None
    assert by_nr[1]["r2_co2"] > 0.9
    assert "dropped_nan" in by_nr[1]["flags"]
    assert by_nr[1]["temperature_used_c"] is not None
    assert by_nr[1]["time_offset_applied_s"] == 0

    # Spot 2: flat window -> low R².
    assert "low_r2" in by_nr[2]["flags"]

    # Skipped spots carry a reason and null fluxes.
    assert by_nr[3]["skipped"] is True
    assert by_nr[3]["skip_reason"] == "empty window"
    assert by_nr[3]["co2_flux_umol_m2_s"] is None
    assert by_nr[4]["skipped"] is True
    assert by_nr[4]["skip_reason"] == "stop before start"


def test_spot_detail(client: TestClient) -> None:
    analysis_id = _create_and_match(client)
    resp = client.get(f"/api/analyses/{analysis_id}/spots/1")
    assert resp.status_code == 200
    detail = resp.json()
    assert set(detail["gases"]) == {"CO2", "CH4"}

    co2 = detail["gases"]["CO2"]
    assert co2["unit"] == "ppm"
    assert len(co2["points"]) > 100
    assert any(p["in_window"] for p in co2["points"])
    assert any(not p["in_window"] for p in co2["points"])  # first 30 s excluded
    assert co2["fit"]["n_points"] > 0
    assert co2["fit"]["n_dropped_nan"] >= 1
    assert co2["flux_ladder"]["umol_m2_s"] != 0.0
    assert detail["fit_window"]["start"] == "09:38:30"
    assert detail["fit_window"]["stop"] == "09:43:30"


def test_spot_detail_skipped_is_null(client: TestClient) -> None:
    analysis_id = _create_and_match(client)
    resp = client.get(f"/api/analyses/{analysis_id}/spots/3")  # empty-window skip
    assert resp.status_code == 200
    assert resp.json() is None


def test_log_endpoint(client: TestClient) -> None:
    analysis_id = _create_and_match(client)
    resp = client.get(f"/api/analyses/{analysis_id}/log")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) > 0
    assert {"ts", "severity", "message"} <= set(entries[0])
    assert any("time-offset" in e["message"] for e in entries)


def test_read_endpoints_404(client: TestClient) -> None:
    assert client.get("/api/analyses/nope/results").status_code == 404
    assert client.get("/api/analyses/nope/log").status_code == 404
    analysis_id = _create_and_match(client)
    assert client.get(f"/api/analyses/{analysis_id}/spots/999").status_code == 404


def test_timeseries_endpoint(client: TestClient) -> None:
    analysis_id = _create_and_match(client)
    resp = client.get(f"/api/analyses/{analysis_id}/timeseries")
    assert resp.status_code == 200
    ts = resp.json()
    assert ts["co2"]["unit"] == "ppm" and ts["ch4"]["unit"] == "ppb"
    # Computed spots (1 & 2) carry points on the absolute time axis + a fit line.
    co2_spots = {s["nr"]: s for s in ts["co2"]["spots"]}
    assert 1 in co2_spots
    spot = co2_spots[1]
    assert len(spot["points"]) > 100
    assert spot["points"][0]["t_unix"] > 1_700_000_000  # real unix seconds
    assert any(p["in_window"] for p in spot["points"])
    assert len(spot["line"]) == 2  # fit-line endpoints
