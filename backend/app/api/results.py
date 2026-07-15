"""Read endpoints: results table, per-spot detail, processing log (read-only).

Per-spot fits are recomputed from the persisted ``Reading`` rows via the same
``fit_spot`` pipeline the match step used — one code path, deterministic given the
stored readings. ``FluxResult`` remains the durable record used by the export.
"""

import pandas as pd
from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.errors import api_error
from app.db.models import Analysis, Reading, Spot
from app.db.session import get_session
from app.flux import constants as C
from app.flux.pipeline import GAS_COLUMN, GasResult, fit_spot
from app.schemas.results import (
    FitWindow,
    FluxLadder,
    GasDetail,
    GasFit,
    GasPoint,
    LogEntry,
    QualityCheck,
    ResultsPayload,
    SpotDetail,
    SpotResult,
)

router = APIRouter(prefix="/api", tags=["results"])

# Canonical order for the per-spot flag list (matches the frontend SpotFlag union).
_FLAG_ORDER = [
    "low_r2",
    "short_window",
    "time_shifted",
    "dropped_nan",
    "no_pressure",
    "anomalous",
]

# gas -> (reading attribute, display unit)
_GAS_META = {"CO2": ("co2_ppm", "ppm"), "CH4": ("ch4_ppb", "ppb")}


def _get_analysis(session: Session, analysis_id: str) -> Analysis:
    analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        raise api_error(404, "not_found", f"Analysis {analysis_id} not found.")
    return analysis


def _sorted_readings(spot: Spot) -> list[Reading]:
    return sorted(spot.readings, key=lambda r: r.timestamp)


def _readings_df(readings: list[Reading]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [r.timestamp for r in readings],
            "co2_ppm": [
                float("nan") if r.co2_ppm is None else r.co2_ppm for r in readings
            ],
            "ch4_ppb": [
                float("nan") if r.ch4_ppb is None else r.ch4_ppb for r in readings
            ],
            "temperature_used": [
                float("nan") if r.temperature_used is None else r.temperature_used
                for r in readings
            ],
        }
    )


def _skip_reason(spot: Spot) -> str:
    if not spot.start_time or not spot.stop_time:
        return "unparseable time"
    if spot.stop_time <= spot.start_time:
        return "stop before start"
    return "empty window"


def _spot_flags(
    results: dict[str, GasResult], *, no_pressure: bool = False
) -> list[str]:
    flags: set[str] = set()
    for gas_result in results.values():
        flags.update(gas_result.flags)  # low_r2, short_window
        if gas_result.n_dropped_nan > 0:
            flags.add("dropped_nan")
        if gas_result.fit_offset_s != C.FIT_SKIP_SECONDS:
            flags.add("time_shifted")  # best-window shifted the fit window
    if no_pressure:
        flags.add("no_pressure")
    return [flag for flag in _FLAG_ORDER if flag in flags]


def _shift_hhmmss(hhmmss: str, seconds: int) -> str:
    hour, minute, second = (int(part) for part in hhmmss.split(":"))
    total = (hour * 3600 + minute * 60 + second + seconds) % 86400
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def _fit_results(
    analysis: Analysis, readings: list[Reading]
) -> dict[str, GasResult] | None:
    """Recompute both gases from persisted readings; None if unfittable."""
    if not readings:
        return None
    temps = [r.temperature_used for r in readings if r.temperature_used is not None]
    if not temps:
        return None  # no temperature at all -> can't compute
    # Pressure is optional: recompute with the default when none was stored (the
    # same fallback the match endpoint used); the spot is flagged no_pressure.
    pressure = readings[0].pressure_used
    if pressure is None:
        pressure = C.DEFAULT_PRESSURE_HPA
    # fit_spot uses the per-reading temperature column for its window mean/range;
    # the scalar here is only a fallback if that column is entirely missing.
    return fit_spot(
        _readings_df(readings),
        analysis.chamber_area_m2,
        analysis.chamber_volume_l,
        sum(temps) / len(temps),
        pressure,
    )


@router.get("/analyses/{analysis_id}/results", response_model=ResultsPayload)
def get_results(
    analysis_id: str, session: Session = Depends(get_session)
) -> ResultsPayload:
    analysis = _get_analysis(session, analysis_id)
    offset = analysis.time_offset_seconds
    date = str(analysis.work_date)

    spots: list[SpotResult] = []
    for spot in sorted(analysis.spots, key=lambda s: s.nr):
        base = dict(
            nr=spot.nr,
            date=date,
            start=spot.start_time,
            stop=spot.stop_time,
            gps=spot.gps,
            light_dark=spot.light_dark,
            location=spot.location_desc,
            time_offset_applied_s=offset,
        )
        readings = _sorted_readings(spot)

        if not readings:
            spots.append(
                SpotResult(
                    **base,
                    co2_flux_umol_m2_s=None,
                    ch4_flux_umol_m2_s=None,
                    r2_co2=None,
                    r2_ch4=None,
                    temperature_used_c=None,
                    pressure_used_hpa=None,
                    n_points_co2=0,
                    n_points_ch4=0,
                    flags=[],
                    skipped=True,
                    skip_reason=_skip_reason(spot),
                )
            )
            continue

        temp = readings[0].temperature_used
        no_pressure = readings[0].pressure_used is None
        # What pressure the flux actually used: the stored value, or the default
        # when none was supplied (pressure is optional).
        pressure = C.DEFAULT_PRESSURE_HPA if no_pressure else readings[0].pressure_used
        fits = _fit_results(analysis, readings)
        if fits is None:
            # Readings exist but temperature missing -> flux not computed.
            spots.append(
                SpotResult(
                    **base,
                    co2_flux_umol_m2_s=None,
                    ch4_flux_umol_m2_s=None,
                    r2_co2=None,
                    r2_ch4=None,
                    temperature_used_c=temp,
                    pressure_used_hpa=pressure,
                    n_points_co2=0,
                    n_points_ch4=0,
                    flags=["no_pressure"] if no_pressure else [],
                    skipped=False,
                    skip_reason=None,
                )
            )
            continue

        co2, ch4 = fits["CO2"], fits["CH4"]
        spots.append(
            SpotResult(
                **base,
                co2_flux_umol_m2_s=co2.ladder.umol_m2_s if co2.ladder else None,
                ch4_flux_umol_m2_s=ch4.ladder.umol_m2_s if ch4.ladder else None,
                r2_co2=co2.fit.r2 if co2.fit else None,
                r2_ch4=ch4.fit.r2 if ch4.fit else None,
                temperature_used_c=co2.temp_mean_c,
                temperature_min_c=co2.temp_min_c,
                temperature_max_c=co2.temp_max_c,
                pressure_used_hpa=pressure,
                fit_offset_s=co2.fit_offset_s,
                n_points_co2=co2.n_points,
                n_points_ch4=ch4.n_points,
                flags=_spot_flags(fits, no_pressure=no_pressure),
                skipped=False,
                skip_reason=None,
            )
        )

    return ResultsPayload(
        quality_check=QualityCheck(
            available=False,
            summary=(
                "Automatic quality check unavailable — the n8n workflow is not "
                "configured yet."
            ),
            flags=[],
        ),
        # TODO: n8n quality check (later seminar) — populate available/summary/flags.
        spots=spots,
    )


def _gas_detail(
    gas: str, readings: list[Reading], result: GasResult, t0: float
) -> GasDetail:
    attr, unit = _GAS_META[gas]
    points: list[GasPoint] = []
    for reading in readings:
        value = getattr(reading, attr)
        if value is None:
            continue  # nan rows aren't plottable
        rel = reading.timestamp - t0
        points.append(
            GasPoint(
                t_s=rel,
                value=value,
                in_window=result.fit_start_s <= rel < result.fit_stop_s,
            )
        )

    if result.fit is not None and result.ladder is not None:
        fit = GasFit(
            slope=result.fit.slope,
            intercept=result.fit.intercept,
            r2=result.fit.r2,
            n_points=result.fit.n_points,
            n_dropped_nan=result.n_dropped_nan,
        )
        ladder = result.ladder
        flux_ladder = FluxLadder(
            umol_m2_s=ladder.umol_m2_s,
            umol_m2_h=ladder.umol_m2_h,
            mol_m2_h=ladder.mol_m2_h,
            gC_m2_day=ladder.gC_m2_day,
            kg_m2_h=ladder.kg_m2_h,
            kg_ha_h=ladder.kg_ha_h,
            kg_ha_day=ladder.kg_ha_day,
            kg_ha_year=ladder.kg_ha_year,
            Mg_ha_year=ladder.Mg_ha_year,
            Mg_ha_year_co2equiv=ladder.Mg_ha_year_co2equiv,
        )
    else:
        # Gas skipped (too few points): expose the points with a zeroed fit.
        fit = GasFit(
            slope=0.0,
            intercept=0.0,
            r2=0.0,
            n_points=result.n_points,
            n_dropped_nan=result.n_dropped_nan,
        )
        flux_ladder = FluxLadder(
            umol_m2_s=0.0,
            umol_m2_h=0.0,
            mol_m2_h=0.0,
            gC_m2_day=0.0,
            kg_m2_h=0.0,
            kg_ha_h=0.0,
            kg_ha_day=0.0,
            kg_ha_year=0.0,
            Mg_ha_year=0.0,
            Mg_ha_year_co2equiv=0.0,
        )
    return GasDetail(unit=unit, points=points, fit=fit, flux_ladder=flux_ladder)


@router.get("/analyses/{analysis_id}/spots/{nr}", response_model=SpotDetail | None)
def get_spot_detail(
    analysis_id: str, nr: int, session: Session = Depends(get_session)
) -> SpotDetail | None:
    analysis = _get_analysis(session, analysis_id)
    spot = next((s for s in analysis.spots if s.nr == nr), None)
    if spot is None:
        raise api_error(404, "not_found", f"Spot {nr} not found.")

    readings = _sorted_readings(spot)
    fits = _fit_results(analysis, readings)
    if fits is None:
        return None  # skipped spot / no computable detail

    t0 = readings[0].timestamp
    gases = {gas: _gas_detail(gas, readings, fits[gas], t0) for gas in GAS_COLUMN}
    # Both gases share one chosen window per spot; use it for the header times.
    offset = int(fits["CO2"].fit_offset_s)
    return SpotDetail(
        nr=spot.nr,
        gps=spot.gps,
        light_dark=spot.light_dark,
        fit_window=FitWindow(
            start=_shift_hhmmss(spot.start_time, offset),
            stop=_shift_hhmmss(spot.start_time, offset + C.FIT_WINDOW_SECONDS),
        ),
        flags=_spot_flags(fits, no_pressure=readings[0].pressure_used is None),
        gases=gases,
    )


@router.get("/analyses/{analysis_id}/log", response_model=list[LogEntry])
def get_log(
    analysis_id: str, session: Session = Depends(get_session)
) -> list[LogEntry]:
    analysis = _get_analysis(session, analysis_id)
    entries = sorted(analysis.log_entries, key=lambda e: (e.ts, e.id))
    return [LogEntry(ts=e.ts, severity=e.severity, message=e.message) for e in entries]
