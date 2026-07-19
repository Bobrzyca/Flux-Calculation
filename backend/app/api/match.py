"""Match & compute endpoint — where the pure modules come together.

``POST /api/analyses/{id}/match`` parses the stored files, applies the offset,
slices per-spot windows, attaches temperature/pressure, fits both gases, computes
the ladder, and persists Reading + FluxResult + processing-log rows. Re-running
clears the previous results first (supports the overwrite re-run). The endpoint
stays thin — all math lives in ``flux/`` and ``matching/``.
"""

from datetime import UTC, datetime

import pandas as pd
from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.errors import api_error
from app.db import storage
from app.db.models import Analysis, FluxResult, ProcessingLogEntry, Reading
from app.db.session import get_session
from app.flux.constants import DEFAULT_PRESSURE_HPA, FIT_WINDOW_SECONDS
from app.flux.pipeline import fit_spot
from app.matching.match import match_spot
from app.parsing.li7810 import parse_li7810
from app.parsing.pressure import parse_pressure
from app.parsing.temperature import parse_temperature
from app.schemas.match import MatchSummary

router = APIRouter(prefix="/api", tags=["match"])


def _num(value: float) -> float | None:
    """Map a pandas nan to SQL NULL; otherwise a plain float."""
    return None if pd.isna(value) else float(value)


def _clear_previous(session: Session, analysis: Analysis) -> None:
    """Drop prior Reading/FluxResult/log rows so a re-run recomputes cleanly."""
    for spot in analysis.spots:
        for reading in spot.readings:
            session.delete(reading)
        for flux in spot.flux_results:
            session.delete(flux)
    for entry in analysis.log_entries:
        session.delete(entry)
    session.flush()
    # Reload the analysis's relationship collections so they no longer reference
    # the just-deleted rows (which would break the later commit's cascade).
    session.expire(analysis)


@router.post("/analyses/{analysis_id}/match", response_model=MatchSummary)
def run_match(
    analysis_id: str, session: Session = Depends(get_session)
) -> MatchSummary:
    analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        raise api_error(404, "not_found", f"Analysis {analysis_id} not found.")

    # Concentration + temperature are required; pressure is optional (default used).
    required = ("concentration", "temperature")
    paths = {
        role: storage.find_stored(analysis_id, role) for role in (*required, "pressure")
    }
    missing = [role for role in required if paths[role] is None]
    if missing:
        raise api_error(
            422,
            "missing_stored_file",
            f"Stored file(s) missing: {', '.join(missing)}.",
        )
    conc_path, temp_path = paths["concentration"], paths["temperature"]
    press_path = paths["pressure"]
    assert conc_path and temp_path  # validated just above

    # Parse the stored files. A malformed file is the user's problem, not a
    # server fault, so surface it as a clean 422 on the right field rather than
    # letting the exception 500 (which the UI would otherwise hang on).
    try:
        readings = parse_li7810(conc_path)
    except (ValueError, OSError) as exc:
        raise api_error(
            422,
            "bad_concentration",
            f"Couldn't read the LI-7810 concentration file: {exc}",
            field="concentration",
        ) from exc
    try:
        temperature = parse_temperature(temp_path)
    except (ValueError, OSError) as exc:
        raise api_error(
            422,
            "bad_temperature",
            "Couldn't read the temperature file — expected an .xlsx or .csv "
            "with a date/time column and a temperature (°C) column.",
            field="temperature",
        ) from exc
    # No pressure file → empty list; nearest_pressure returns None and the flux
    # falls back to the default pressure below (spot flagged no_pressure).
    try:
        pressure = parse_pressure(press_path) if press_path else []
    except (ValueError, OSError) as exc:
        raise api_error(
            422,
            "bad_pressure",
            "Couldn't read the pressure file. Remove it to use the default "
            "pressure, or provide a readable IMGW file.",
            field="pressure",
        ) from exc

    _clear_previous(session, analysis)

    logs: list[tuple[str, str]] = []
    offset = analysis.time_offset_seconds
    logs.append(
        ("info", f"Applied time-offset {offset:+g} s to {len(readings)} readings")
    )

    # The note windows are HH:MM only, so they need a date. The concentration
    # file is authoritative (its DATE column), so derive the work date from it
    # rather than trusting the hand-typed form field — a wrong date there would
    # otherwise put every window on the wrong day and match nothing.
    work_date = analysis.work_date
    valid_ts = readings["timestamp"].dropna()
    if not valid_ts.empty:
        data_date = datetime.fromtimestamp(float(valid_ts.min()), tz=UTC).date()
        if data_date != analysis.work_date:
            logs.append(
                (
                    "info",
                    f"Matching against the concentration date {data_date} "
                    f"(the form said {analysis.work_date}).",
                )
            )
            analysis.work_date = data_date  # correct the record for display/export
        work_date = data_date

    spots = sorted(analysis.spots, key=lambda s: s.nr)
    spots_computed = 0
    flux_count = 0

    for spot in spots:
        matched = match_spot(
            spot.nr,
            readings,
            spot.start_time,
            spot.stop_time,
            work_date,
            offset,
            temperature,
            pressure,
        )
        logs.extend((m.severity, m.message) for m in matched.logs)
        if matched.skipped:
            continue

        window = matched.readings
        for row in window.itertuples(index=False):
            session.add(
                Reading(
                    spot_id=spot.id,
                    timestamp=float(row.timestamp),
                    co2_ppm=_num(row.co2_ppm),
                    ch4_ppb=_num(row.ch4_ppb),
                    temperature_used=_num(row.temperature_used),
                    pressure_used=matched.pressure_used,
                )
            )

        if matched.temperature_used is None:
            logs.append(
                (
                    "warning",
                    f"Spot {spot.nr}: flux not computed (missing temperature)",
                )
            )
            spots_computed += 1
            continue

        # Pressure is optional: fall back to the default when none was matched.
        pressure_for_flux = matched.pressure_used
        if pressure_for_flux is None:
            pressure_for_flux = DEFAULT_PRESSURE_HPA
            logs.append(
                (
                    "info",
                    f"Spot {spot.nr}: no pressure file — assuming 1 atm "
                    f"({DEFAULT_PRESSURE_HPA:.2f} hPa)",
                )
            )

        logs.append(
            (
                "info",
                f"Spot {spot.nr}: matched temperature "
                f"{matched.temperature_used:.2f} °C, pressure "
                f"{pressure_for_flux:.1f} hPa to {len(window)} readings",
            )
        )
        results = fit_spot(
            window,
            analysis.chamber_area_m2,
            analysis.chamber_volume_l,
            matched.temperature_used,
            pressure_for_flux,
            manual_offset_s=spot.manual_offset_s,
        )
        chosen = next(iter(results.values()))
        # NB: deliberately NOT named `offset` — that variable is the analysis's
        # instrument-clock offset, and shadowing it here once shifted every
        # subsequent spot's window by the previous spot's fit offset.
        fit_off, length = chosen.fit_offset_s, chosen.fit_window_s
        logs.append(
            (
                "info",
                f"Spot {spot.nr}: fit window = start +{int(fit_off)} s → +"
                f"{int(fit_off + length)} s "
                f"(most-linear {int(length)} s window)",
            )
        )
        if chosen.window_shortened:
            logs.append(
                (
                    "warning",
                    f"Spot {spot.nr}: window shortened to {int(length)} s "
                    f"(< {FIT_WINDOW_SECONDS} s) to improve a low R²",
                )
            )
        for gas, gr in results.items():
            if gr.n_spikes:
                logs.append(
                    (
                        "info",
                        f"Spot {spot.nr} {gas}: {gr.n_spikes} isolated spike"
                        f"{'s' if gr.n_spikes != 1 else ''} dropped",
                    )
                )
            if gr.skipped or gr.fit is None or gr.ladder is None:
                logs.append(
                    ("warning", f"Spot {spot.nr} {gas}: skipped ({gr.skip_reason})")
                )
                continue
            ladder = gr.ladder
            session.add(
                FluxResult(
                    spot_id=spot.id,
                    gas=gas,
                    slope=gr.fit.slope,
                    r2=gr.fit.r2,
                    flux_umol_m2_s=ladder.umol_m2_s,
                    flux_umol_m2_h=ladder.umol_m2_h,
                    flux_mol_m2_h=ladder.mol_m2_h,
                    flux_gC_m2_day=ladder.gC_m2_day,
                    flux_kg_m2_h=ladder.kg_m2_h,
                    flux_kg_ha_h=ladder.kg_ha_h,
                    flux_kg_ha_day=ladder.kg_ha_day,
                    flux_kg_ha_year=ladder.kg_ha_year,
                    flux_Mg_ha_year=ladder.Mg_ha_year,
                    flux_Mg_ha_year_co2equiv=ladder.Mg_ha_year_co2equiv,
                    n_points=gr.fit.n_points,
                )
            )
            flux_count += 1
            logs.append(
                (
                    "info",
                    f"Spot {spot.nr} {gas}: slope={gr.fit.slope:.5g}, "
                    f"R²={gr.fit.r2:.3f}, n={gr.fit.n_points}",
                )
            )
            if gr.n_dropped_nan:
                total = gr.n_points + gr.n_dropped_nan
                logs.append(
                    (
                        "info",
                        f"Spot {spot.nr} {gas}: {gr.n_dropped_nan} of {total} "
                        "readings dropped (nan)",
                    )
                )
            for flag in gr.flags:
                logs.append(("warning", f"Spot {spot.nr} {gas}: {flag}"))
        spots_computed += 1

    for severity, message in logs:
        session.add(
            ProcessingLogEntry(
                analysis_id=analysis_id, severity=severity, message=message
            )
        )
    analysis.status = "complete"
    session.add(analysis)
    session.commit()

    return MatchSummary(
        status="complete",
        spots_total=len(spots),
        spots_computed=spots_computed,
        spots_skipped=len(spots) - spots_computed,
        flux_results=flux_count,
    )
