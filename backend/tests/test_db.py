"""Persistence layer: models, relationships, and the full flux unit ladder.

Uses an in-memory SQLite engine (StaticPool so it survives multiple sessions)
so the test never touches the real ``data/`` directory.
"""

from datetime import date, datetime

from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.db.models import (
    Analysis,
    FluxResult,
    ProcessingLogEntry,
    Reading,
    Spot,
)

# Every unit-ladder column the brief requires on FluxResult.
LADDER_COLUMNS = {
    "flux_umol_m2_s",
    "flux_umol_m2_h",
    "flux_mol_m2_h",
    "flux_gC_m2_day",
    "flux_kg_m2_h",
    "flux_kg_ha_h",
    "flux_kg_ha_day",
    "flux_kg_ha_year",
    "flux_Mg_ha_year",
    "flux_Mg_ha_year_co2equiv",
}


def _make_engine() -> Engine:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def test_flux_result_has_full_ladder() -> None:
    assert LADDER_COLUMNS <= set(FluxResult.model_fields)


def test_analysis_with_children_roundtrip() -> None:
    engine = _make_engine()

    with Session(engine) as session:
        analysis = Analysis(
            name="Kampinos 2 July",
            work_date=date(2026, 7, 2),
            chamber_area_m2=0.0625,
            chamber_volume_l=15.625,
            time_offset_seconds=-3.0,
        )
        spot = Spot(
            nr=1,
            gps="52.30,20.55",
            light_dark="light",
            location_desc="dam edge",
            start_time="09:38:00",
            stop_time="09:44:00",
        )
        spot.readings.append(
            Reading(
                timestamp=1751442000.0,
                co2_ppm=412.5,
                ch4_ppb=1975.0,
                temperature_used=18.2,
                pressure_used=1013.2,
            )
        )
        # A nan-dropped row is represented as null concentrations.
        spot.readings.append(
            Reading(
                timestamp=1751442001.0,
                co2_ppm=None,
                ch4_ppb=None,
                temperature_used=18.2,
                pressure_used=1013.2,
            )
        )
        for gas in ("CO2", "CH4"):
            spot.flux_results.append(
                FluxResult(
                    gas=gas,
                    slope=0.0123,
                    r2=0.987,
                    flux_umol_m2_s=1.0,
                    flux_umol_m2_h=3600.0,
                    flux_mol_m2_h=0.0036,
                    flux_gC_m2_day=1.036,
                    flux_kg_m2_h=1e-6,
                    flux_kg_ha_h=0.01,
                    flux_kg_ha_day=0.24,
                    flux_kg_ha_year=87.6,
                    flux_Mg_ha_year=0.0876,
                    flux_Mg_ha_year_co2equiv=0.0876,
                    n_points=300,
                )
            )
        analysis.spots.append(spot)
        analysis.log_entries.append(
            ProcessingLogEntry(
                severity="warning",
                message="Spot 1: 1 of 2 readings dropped (nan)",
            )
        )
        session.add(analysis)
        session.commit()
        analysis_id = analysis.id

    # Fresh session proves the rows were persisted, not just cached.
    with Session(engine) as session:
        loaded = session.get(Analysis, analysis_id)
        assert loaded is not None
        assert loaded.id  # non-empty, URL-safe id assigned
        assert loaded.status == "draft"  # default
        assert isinstance(loaded.created_at, datetime)
        assert loaded.work_date == date(2026, 7, 2)

        assert len(loaded.spots) == 1
        got_spot = loaded.spots[0]
        assert got_spot.analysis_id == analysis_id
        assert got_spot.start_time == "09:38:00"
        assert len(got_spot.readings) == 2
        assert {r.co2_ppm for r in got_spot.readings} == {412.5, None}

        assert len(got_spot.flux_results) == 2
        assert {fr.gas for fr in got_spot.flux_results} == {"CO2", "CH4"}
        co2 = next(fr for fr in got_spot.flux_results if fr.gas == "CO2")
        assert co2.flux_Mg_ha_year_co2equiv == 0.0876
        assert co2.n_points == 300

        entries = session.exec(
            select(ProcessingLogEntry).where(
                ProcessingLogEntry.analysis_id == analysis_id
            )
        ).all()
        assert len(entries) == 1
        assert entries[0].severity == "warning"
