"""End-to-end: drive the whole pipeline through the HTTP API in one test.

create -> GET notes -> PUT confirmed notes -> POST match -> GET results / a spot
detail / the log -> export. Asserts the numbers are stable and the skipped /
low-R² spots behave as expected.

Scientific validation: the R method-of-record (`reference/`) is not in the repo
yet, so we assert against the flux math locked by hand-computed values in
tests/test_flux.py (chunk 6). TODO: cross-check against the cleaned R script on
the 2026-07-02 Kampinos campaign once reference/ lands.
"""

from fastapi.testclient import TestClient

from tests.conftest import sample_files, sample_form


def test_full_pipeline_over_http(client: TestClient) -> None:
    # 1. Create.
    created = client.post(
        "/api/analyses", data=sample_form(name="E2E Kampinos"), files=sample_files()
    )
    assert created.status_code == 201
    analysis = created.json()
    analysis_id = analysis["id"]
    assert analysis["status"] == "needs_review"
    assert analysis["spot_count"] == 4

    # 2. Read parsed notes (Confirm screen).
    notes = client.get(f"/api/analyses/{analysis_id}/notes").json()
    assert notes["parse_failed"] is False
    assert {r["nr"] for r in notes["rows"]} == {1, 2, 3, 4}

    # 3. Confirm the notes unchanged.
    put = client.put(f"/api/analyses/{analysis_id}/notes", json=notes["rows"])
    assert put.status_code == 200

    # 4. Match & compute.
    summary = client.post(f"/api/analyses/{analysis_id}/match").json()
    assert summary["status"] == "complete"
    assert summary["spots_computed"] == 2
    assert summary["spots_skipped"] == 2
    assert summary["flux_results"] == 4

    # 5. Results.
    results = client.get(f"/api/analyses/{analysis_id}/results").json()
    assert results["quality_check"]["available"] is False
    by_nr = {s["nr"]: s for s in results["spots"]}

    # Scientific validation: spot 1 is the clean rise (~0.03 ppm/s over the fit
    # window, 0.0625 m² / 15.625 L, ~18 °C, ~1013 hPa) -> ~0.31 µmol·m⁻²·s⁻¹.
    spot1 = by_nr[1]
    assert spot1["r2_co2"] > 0.999
    assert 0.30 < spot1["co2_flux_umol_m2_s"] < 0.33
    assert "dropped_nan" in spot1["flags"]

    # Spot 2 flat window -> low R²; spots 3 & 4 skipped with reasons.
    assert "low_r2" in by_nr[2]["flags"]
    assert by_nr[3]["skipped"] and by_nr[3]["skip_reason"] == "empty window"
    assert by_nr[4]["skipped"] and by_nr[4]["skip_reason"] == "stop before start"

    # 6. Spot detail + 7. log.
    detail = client.get(f"/api/analyses/{analysis_id}/spots/1").json()
    assert set(detail["gases"]) == {"CO2", "CH4"}
    co2_detail = detail["gases"]["CO2"]
    assert co2_detail["flux_ladder"]["umol_m2_s"] == spot1["co2_flux_umol_m2_s"]
    log = client.get(f"/api/analyses/{analysis_id}/log").json()
    assert any("time-offset" in e["message"] for e in log)

    # 8. Export.
    export = client.get(f"/api/analyses/{analysis_id}/export?format=txt")
    assert export.status_code == 200
    assert len(export.text.strip().split("\n")) == 1 + 4

    # Numbers are stable: a second match yields identical results.
    client.post(f"/api/analyses/{analysis_id}/match")
    results2 = client.get(f"/api/analyses/{analysis_id}/results").json()
    assert results2 == results
