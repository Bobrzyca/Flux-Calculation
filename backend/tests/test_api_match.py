"""Match & compute endpoint: persistence, skips, flags, idempotent re-run."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.models import Analysis
from tests.conftest import sample_files, sample_form


def _create(client: TestClient) -> str:
    return str(
        client.post("/api/analyses", data=sample_form(), files=sample_files()).json()[
            "id"
        ]
    )


def test_match_computes_and_persists(client: TestClient, session: Session) -> None:
    analysis_id = _create(client)
    resp = client.post(f"/api/analyses/{analysis_id}/match")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["status"] == "complete"
    # Spots 1 & 2 have data; spot 3's window is outside the stream (empty), spot 4
    # stops before it starts — both skipped.
    assert summary["spots_computed"] == 2
    assert summary["spots_skipped"] == 2
    assert summary["flux_results"] == 4

    analysis = session.get(Analysis, analysis_id)
    assert analysis is not None
    assert analysis.status == "complete"
    spots = {s.nr: s for s in analysis.spots}

    # Spot 1: readings persisted + two flux results with a clean CO2 fit.
    assert len(spots[1].readings) > 100
    assert len(spots[1].flux_results) == 2
    co2 = next(f for f in spots[1].flux_results if f.gas == "CO2")
    assert co2.r2 > 0.9
    assert co2.flux_umol_m2_s != 0.0
    assert co2.n_points > 0
    # Some readings were dropped as nan inside the window -> stored as NULL.
    assert any(r.co2_ppm is None for r in spots[1].readings)

    # Skipped spots produced nothing.
    assert spots[3].readings == [] and spots[3].flux_results == []
    assert spots[4].readings == [] and spots[4].flux_results == []

    # The processing log recorded the run: offset, a skip, the matched
    # temperature/pressure, and a per-gas fit summary.
    messages = [e.message for e in analysis.log_entries]
    assert any("time-offset" in m for m in messages)
    assert any("skipped" in m.lower() for m in messages)
    assert any("matched temperature" in m for m in messages)
    assert any("slope=" in m and "R²=" in m for m in messages)


def test_low_r2_spot_still_computes(client: TestClient, session: Session) -> None:
    analysis_id = _create(client)
    client.post(f"/api/analyses/{analysis_id}/match")
    analysis = session.get(Analysis, analysis_id)
    assert analysis is not None
    spot2 = next(s for s in analysis.spots if s.nr == 2)
    # Spot 2 is the flat/noisy window -> low R², but flux is still computed.
    assert len(spot2.flux_results) == 2
    assert min(f.r2 for f in spot2.flux_results) < 0.80


def test_match_without_pressure_uses_default(
    client: TestClient, session: Session
) -> None:
    # Create an analysis with no pressure file, then match: flux is still computed
    # (using the default pressure) and every computed spot is flagged no_pressure.
    files = sample_files()
    del files["pressure"]
    analysis_id = str(
        client.post(
            "/api/analyses", data=sample_form(name="No pressure"), files=files
        ).json()["id"]
    )

    summary = client.post(f"/api/analyses/{analysis_id}/match").json()
    assert summary["status"] == "complete"
    assert summary["spots_computed"] == 2
    assert summary["flux_results"] == 4  # flux still computed via default pressure

    # Every computed spot carries the no_pressure flag in the results.
    results = client.get(f"/api/analyses/{analysis_id}/results").json()
    computed = [s for s in results["spots"] if not s["skipped"]]
    assert computed
    assert all("no_pressure" in s["flags"] for s in computed)

    analysis = session.get(Analysis, analysis_id)
    assert analysis is not None
    messages = [e.message for e in analysis.log_entries]
    assert any("1 atm" in m and "hPa" in m for m in messages)


def test_match_derives_date_from_concentration(
    client: TestClient, session: Session
) -> None:
    # A wrong hand-typed work_date must not break matching: the concentration
    # file's own date is authoritative and is used (and recorded) instead.
    form = sample_form(name="Wrong date")
    form["work_date"] = "2026-07-14"  # sample data is actually 2026-07-02
    aid = client.post("/api/analyses", data=form, files=sample_files()).json()["id"]

    summary = client.post(f"/api/analyses/{aid}/match").json()
    assert summary["spots_computed"] == 2  # matched despite the wrong form date

    analysis = session.get(Analysis, aid)
    assert analysis is not None
    assert str(analysis.work_date) == "2026-07-02"  # corrected to the data's date


def test_match_is_idempotent(client: TestClient, session: Session) -> None:
    analysis_id = _create(client)
    first = client.post(f"/api/analyses/{analysis_id}/match").json()
    second = client.post(f"/api/analyses/{analysis_id}/match").json()
    assert first == second

    # No duplicate rows accumulated on the second run.
    analysis = session.get(Analysis, analysis_id)
    assert analysis is not None
    spot1 = next(s for s in analysis.spots if s.nr == 1)
    assert len(spot1.flux_results) == 2


def test_match_unknown_analysis_404(client: TestClient) -> None:
    assert client.post("/api/analyses/nope/match").status_code == 404
