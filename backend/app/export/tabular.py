"""Build the export table from an analysis (reusable across formats).

Rows come from the persisted `FluxResult` records (the durable result of the
match step) so the export carries the **full unit ladder** for each gas — the
point of the download versus the on-screen table.
"""

from typing import Any

from app.db.models import Analysis, Reading

# The unit-ladder fields in export order; each maps to a FluxResult ``flux_*`` column.
_LADDER = [
    "umol_m2_s",
    "umol_m2_h",
    "mol_m2_h",
    "gC_m2_day",
    "kg_m2_h",
    "kg_ha_h",
    "kg_ha_day",
    "kg_ha_year",
    "Mg_ha_year",
    "Mg_ha_year_co2equiv",
]
_GASES = ("CO2", "CH4")


def _headers() -> list[str]:
    headers = [
        "Nr",
        "date",
        "start",
        "stop",
        "GPS",
        "light_dark",
        "location",
        "temperature_used_c",
        "pressure_used_hpa",
        "time_offset_applied_s",
    ]
    for gas in _GASES:
        headers.append(f"R2_{gas}")
        headers.append(f"n_points_{gas}")
        headers.extend(f"{gas}_{unit}" for unit in _LADDER)
    headers.extend(["skipped", "skip_reason"])
    return headers


def _skip_reason(spot_start: str, spot_stop: str, has_readings: bool) -> str | None:
    if has_readings:
        return None
    if not spot_start or not spot_stop:
        return "unparseable time"
    if spot_stop <= spot_start:
        return "stop before start"
    return "empty window"


def build_table(analysis: Analysis) -> tuple[list[str], list[list[Any]]]:
    """Return ``(headers, rows)`` — one row per spot, ordered by Nr."""
    rows: list[list[Any]] = []
    for spot in sorted(analysis.spots, key=lambda s: s.nr):
        readings: list[Reading] = list(spot.readings)
        flux_by_gas = {fr.gas: fr for fr in spot.flux_results}
        temp = readings[0].temperature_used if readings else None
        pressure = readings[0].pressure_used if readings else None

        row: list[Any] = [
            spot.nr,
            str(analysis.work_date),
            spot.start_time,
            spot.stop_time,
            spot.gps,
            spot.light_dark,
            spot.location_desc,
            temp,
            pressure,
            analysis.time_offset_seconds,
        ]
        for gas in _GASES:
            fr = flux_by_gas.get(gas)
            if fr is None:
                row.extend(["", ""] + ["" for _ in _LADDER])
            else:
                row.append(fr.r2)
                row.append(fr.n_points)
                row.extend(getattr(fr, f"flux_{unit}") for unit in _LADDER)
        row.append(bool(not readings))
        row.append(_skip_reason(spot.start_time, spot.stop_time, bool(readings)))
        rows.append(row)

    return _headers(), rows
