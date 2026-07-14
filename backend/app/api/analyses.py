"""Analysis lifecycle endpoints: create (multipart upload), list, get, delete.

On create we store the four raw files, validate the LI-7810 format, persist the
``Analysis`` (status ``needs_review``), and parse the notes into unconfirmed
``Spot`` rows so the Confirm screen has something to show.
"""

import os
import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlmodel import Session, col, select

from app.api.errors import api_error
from app.db import storage
from app.db.models import Analysis, ProcessingLogEntry, Spot
from app.db.session import get_session
from app.parsing.li7810 import looks_like_li7810
from app.parsing.notes import parse_notes, validate_notes
from app.schemas.analysis import AnalysisDetail, AnalysisSummary

router = APIRouter(prefix="/api", tags=["analyses"])

# The four raw inputs, in upload-field order.
_FILE_ROLES = ("concentration", "notes", "temperature", "pressure")

# Per-file upload cap (~50 MB, per the brief).
MAX_UPLOAD_MB = 50
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def _to_detail(analysis: Analysis, spot_count: int) -> AnalysisDetail:
    return AnalysisDetail(
        id=analysis.id,
        name=analysis.name,
        work_date=analysis.work_date,
        spot_count=spot_count,
        status=analysis.status,
        created_at=analysis.created_at,
        chamber_area_m2=analysis.chamber_area_m2,
        chamber_volume_l=analysis.chamber_volume_l,
        time_offset_seconds=analysis.time_offset_seconds,
    )


def _content_looks_like_li7810(filename: str, content: bytes) -> bool:
    """Validate LI-7810 format from in-memory bytes (via a short-lived temp file)."""
    with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        return looks_like_li7810(tmp_path)
    finally:
        os.unlink(tmp_path)


@router.post("/analyses", response_model=AnalysisDetail, status_code=201)
async def create_analysis(
    name: str = Form(...),
    work_date: date = Form(...),
    chamber_area_m2: float = Form(...),
    chamber_volume_l: float = Form(...),
    time_offset_seconds: float = Form(0.0),
    concentration: UploadFile | None = File(None),
    notes: UploadFile | None = File(None),
    temperature: UploadFile | None = File(None),
    pressure: UploadFile | None = File(None),
    session: Session = Depends(get_session),
) -> AnalysisDetail:
    uploads = {
        "concentration": concentration,
        "notes": notes,
        "temperature": temperature,
        "pressure": pressure,
    }

    # 1. All four files present.
    for role in _FILE_ROLES:
        upload = uploads[role]
        if upload is None or not upload.filename:
            raise api_error(
                422, "missing_file", f"The {role} file is required.", field=role
            )

    contents = {role: await uploads[role].read() for role in _FILE_ROLES}  # type: ignore[union-attr]

    # Reject oversized uploads (protects memory / disk on this local box).
    for role in _FILE_ROLES:
        if len(contents[role]) > MAX_UPLOAD_BYTES:
            raise api_error(
                422,
                "file_too_large",
                f"The {role} file exceeds the {MAX_UPLOAD_MB} MB limit.",
                field=role,
            )

    # 2. The concentration file really is a LI-7810 export.
    conc_name = concentration.filename if concentration else "concentration"
    if not _content_looks_like_li7810(conc_name or "", contents["concentration"]):
        raise api_error(
            422,
            "bad_li7810",
            "This doesn't look like a LI-7810 export — expected columns "
            "SECONDS, CO2, CH4.",
            field="concentration",
        )

    # 3. Reject a duplicate analysis name (frontend offers rename/overwrite).
    existing = session.exec(select(Analysis).where(Analysis.name == name)).first()
    if existing is not None:
        raise api_error(
            409, "duplicate_name", f'An analysis named "{name}" already exists.', "name"
        )

    # 4. Persist the analysis, save files, parse notes into unconfirmed spots.
    analysis = Analysis(
        name=name,
        work_date=work_date,
        chamber_area_m2=chamber_area_m2,
        chamber_volume_l=chamber_volume_l,
        time_offset_seconds=time_offset_seconds,
        status="needs_review",
    )
    session.add(analysis)
    session.flush()  # assign analysis.id before we save files under it

    for role in _FILE_ROLES:
        upload = uploads[role]
        assert upload is not None  # validated above
        storage.save_upload(analysis.id, role, upload.filename or role, contents[role])

    notes_path = storage.find_stored(analysis.id, "notes")
    rows = validate_notes(parse_notes(notes_path)) if notes_path else []
    for note in rows:
        session.add(
            Spot(
                analysis_id=analysis.id,
                nr=note.nr,
                gps=note.gps,
                light_dark=note.light_dark,
                location_desc=note.location,
                start_time=note.start_time,
                stop_time=note.stop_time,
            )
        )

    session.add(
        ProcessingLogEntry(
            analysis_id=analysis.id,
            severity="info",
            message=f"Analysis created; parsed {len(rows)} note rows for review.",
        )
    )
    session.commit()
    session.refresh(analysis)
    return _to_detail(analysis, spot_count=len(rows))


@router.get("/analyses", response_model=list[AnalysisSummary])
def list_analyses(session: Session = Depends(get_session)) -> list[AnalysisSummary]:
    analyses = session.exec(
        select(Analysis).order_by(col(Analysis.created_at).desc())
    ).all()
    return [
        AnalysisSummary(
            id=a.id,
            name=a.name,
            work_date=a.work_date,
            spot_count=len(a.spots),
            status=a.status,
            created_at=a.created_at,
        )
        for a in analyses
    ]


@router.get("/analyses/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(
    analysis_id: str, session: Session = Depends(get_session)
) -> AnalysisDetail:
    analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        raise api_error(404, "not_found", f"Analysis {analysis_id} not found.")
    return _to_detail(analysis, spot_count=len(analysis.spots))


@router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: str, session: Session = Depends(get_session)) -> None:
    analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        raise api_error(404, "not_found", f"Analysis {analysis_id} not found.")
    for spot in analysis.spots:
        for reading in spot.readings:
            session.delete(reading)
        for flux in spot.flux_results:
            session.delete(flux)
        session.delete(spot)
    for entry in analysis.log_entries:
        session.delete(entry)
    session.delete(analysis)
    session.commit()
    storage.delete_analysis_files(analysis_id)
