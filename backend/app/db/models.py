"""SQLModel table models — the persistence schema.

Mirrors ``project-brief.md`` → "Data stored by the application". Five tables:
``Analysis`` (one per campaign) owns ``Spot`` rows; each ``Spot`` owns its
``Reading`` rows (the sliced concentration window) and up to two ``FluxResult``
rows (CO₂ and CH₄). ``ProcessingLogEntry`` persists the campaign-wide audit log.

Primary keys are URL-safe UUID4 hex strings so ids can appear in ``/api`` paths
without escaping. Raw uploaded files are kept on disk (see ``storage.py``) and
referenced by the ``Analysis`` so any campaign can be re-run.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlmodel import Field, Relationship, SQLModel

# NOTE: forward references to later-defined models are quoted string literals
# (e.g. list["Spot"]). We deliberately do NOT use `from __future__ import
# annotations`, which would break SQLModel's relationship resolution (SQLAlchemy
# would see the literal string "list[Spot]"). The per-line UP037 suppressions
# below keep those necessary quotes past ruff's "remove quotes" rule.


def _uuid_hex() -> str:
    """A stable, URL-safe primary key."""
    return uuid4().hex


def _utcnow() -> datetime:
    """Timezone-aware creation timestamp."""
    return datetime.now(UTC)


class Analysis(SQLModel, table=True):
    """One measurement campaign: its inputs, constants, and status."""

    id: str = Field(default_factory=_uuid_hex, primary_key=True)
    name: str
    work_date: date
    chamber_area_m2: float
    chamber_volume_l: float
    time_offset_seconds: float = 0.0
    # Pipeline stage: draft -> needs_review (notes parsed) -> complete (flux done).
    status: str = "draft"
    created_at: datetime = Field(default_factory=_utcnow)

    spots: list["Spot"] = Relationship(back_populates="analysis")  # noqa: UP037
    log_entries: list["ProcessingLogEntry"] = Relationship(  # noqa: UP037
        back_populates="analysis"
    )


class Spot(SQLModel, table=True):
    """One measurement spot (a chamber placement) within an analysis."""

    id: str = Field(default_factory=_uuid_hex, primary_key=True)
    analysis_id: str = Field(foreign_key="analysis.id", index=True)
    nr: int
    gps: str = ""
    light_dark: str = ""
    location_desc: str = ""
    start_time: str  # "HH:MM:SS"
    stop_time: str  # "HH:MM:SS"
    # Manual fit-window override: seconds after the spot's first reading where the
    # fit window should start. None = use the automatic best-window selection.
    manual_offset_s: float | None = Field(default=None)

    analysis: Analysis | None = Relationship(back_populates="spots")
    readings: list["Reading"] = Relationship(back_populates="spot")  # noqa: UP037
    flux_results: list["FluxResult"] = Relationship(  # noqa: UP037
        back_populates="spot"
    )


class Reading(SQLModel, table=True):
    """A single 1 Hz concentration sample inside a spot's window.

    Concentrations are nullable: ``nan`` rows (instrument warm-up or dropouts)
    are stored as null so the dropped-row count is auditable.
    """

    id: str = Field(default_factory=_uuid_hex, primary_key=True)
    spot_id: str = Field(foreign_key="spot.id", index=True)
    timestamp: float  # unix seconds, offset-corrected
    co2_ppm: float | None = None
    ch4_ppb: float | None = None
    temperature_used: float | None = None
    pressure_used: float | None = None

    spot: Spot | None = Relationship(back_populates="readings")


class FluxResult(SQLModel, table=True):
    """The fitted slope, R², and full flux unit ladder for one gas of one spot."""

    id: str = Field(default_factory=_uuid_hex, primary_key=True)
    spot_id: str = Field(foreign_key="spot.id", index=True)
    gas: str  # "CO2" | "CH4"
    slope: float
    r2: float
    # Unit ladder — names match project-brief.md exactly.
    flux_umol_m2_s: float
    flux_umol_m2_h: float
    flux_mol_m2_h: float
    flux_gC_m2_day: float
    flux_kg_m2_h: float
    flux_kg_ha_h: float
    flux_kg_ha_day: float
    flux_kg_ha_year: float
    flux_Mg_ha_year: float
    flux_Mg_ha_year_co2equiv: float
    n_points: int

    spot: Spot | None = Relationship(back_populates="flux_results")


class ProcessingLogEntry(SQLModel, table=True):
    """One line of the campaign-wide processing log (audit trail)."""

    id: str = Field(default_factory=_uuid_hex, primary_key=True)
    analysis_id: str = Field(foreign_key="analysis.id", index=True)
    ts: datetime = Field(default_factory=_utcnow)
    severity: str  # "info" | "warning" | "error"
    message: str

    analysis: Analysis | None = Relationship(back_populates="log_entries")
