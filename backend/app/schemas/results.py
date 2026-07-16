"""Results / per-spot detail / log schemas (mirror the frontend types.ts).

Field names and nullability match ``frontend/src/api/types.ts`` exactly so the
typed client needs no translation layer.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class SpotResult(BaseModel):
    nr: int
    date: str
    start: str
    stop: str
    gps: str
    light_dark: str
    location: str
    co2_flux_umol_m2_s: float | None
    ch4_flux_umol_m2_s: float | None
    r2_co2: float | None
    r2_ch4: float | None
    temperature_used_c: float | None
    temperature_min_c: float | None = None
    temperature_max_c: float | None = None
    pressure_used_hpa: float | None
    time_offset_applied_s: float
    # Seconds the fit window was shifted after the recorded start (best-window).
    fit_offset_s: float = 0.0
    n_points_co2: int
    n_points_ch4: int
    flags: list[str]
    skipped: bool
    skip_reason: str | None


class QualityFlag(BaseModel):
    nr: int
    gps: str
    gas: str
    issue: str
    severity: str


class QualityCheck(BaseModel):
    available: bool
    summary: str | None
    flags: list[QualityFlag]


class ResultsPayload(BaseModel):
    quality_check: QualityCheck
    spots: list[SpotResult]


class GasPoint(BaseModel):
    t_s: float
    value: float
    in_window: bool


class GasFit(BaseModel):
    slope: float
    intercept: float
    r2: float
    n_points: int
    n_dropped_nan: int
    # Isolated single-point spikes dropped from this gas within the fit window.
    n_spikes: int = 0


class FluxLadder(BaseModel):
    umol_m2_s: float
    umol_m2_h: float
    mol_m2_h: float
    gC_m2_day: float
    kg_m2_h: float
    kg_ha_h: float
    kg_ha_day: float
    kg_ha_year: float
    Mg_ha_year: float
    Mg_ha_year_co2equiv: float


class GasDetail(BaseModel):
    unit: str
    points: list[GasPoint]
    fit: GasFit
    flux_ladder: FluxLadder


class FitWindow(BaseModel):
    start: str
    stop: str


class SpotDetail(BaseModel):
    nr: int
    gps: str
    light_dark: str
    fit_window: FitWindow
    # Which fit produced this detail: "auto" (best/shortened window), "full" (the
    # whole recorded window), or "manual" (a saved per-spot offset override).
    mode: str = "auto"
    # Seconds the fit window was shifted after the recorded start (best-window),
    # its length in seconds, and whether it was shortened to recover a low R².
    fit_offset_s: float = 0.0
    fit_window_s: float = 0.0
    window_shortened: bool = False
    # The saved manual offset for this spot (None = automatic). Lets the UI show
    # and pre-fill the current manual correction.
    manual_offset_s: float | None = None
    flags: list[str] = Field(default_factory=list)
    gases: dict[str, GasDetail]


class SpotFitUpdate(BaseModel):
    """Set (or clear) a spot's manual fit-window offset.

    ``offset_s`` is seconds after the spot's first reading where the fixed-length
    fit window should start; ``None`` clears the override and restores the
    automatic best-window selection.
    """

    offset_s: float | None


class LogEntry(BaseModel):
    ts: datetime
    severity: str
    message: str


# --- Whole-campaign time series (for the overview graph) -------------------
class TSPoint(BaseModel):
    t_unix: float  # absolute time (naive local wall-clock as unix seconds)
    value: float
    in_window: bool


class TSLinePoint(BaseModel):
    t_unix: float
    y: float


class TSSpot(BaseModel):
    nr: int
    light_dark: str
    points: list[TSPoint]
    line: list[TSLinePoint]  # fit-line endpoints (empty if not computed)


class TSGas(BaseModel):
    unit: str
    spots: list[TSSpot]


class Timeseries(BaseModel):
    co2: TSGas
    ch4: TSGas
