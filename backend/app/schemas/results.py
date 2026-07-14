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
    pressure_used_hpa: float | None
    time_offset_applied_s: float
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
    flags: list[str] = Field(default_factory=list)
    gases: dict[str, GasDetail]


class LogEntry(BaseModel):
    ts: datetime
    severity: str
    message: str
