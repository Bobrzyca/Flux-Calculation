"""Parsed-notes endpoints backing the Confirm screen (human-in-the-loop).

GET returns the analysis's ``Spot`` rows as ``ParsedNotes`` with freshly computed
flags; PUT replaces them with the user's confirmed/edited rows (re-validated).
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.errors import api_error
from app.db.models import Analysis, Spot
from app.db.session import get_session
from app.parsing.notes import NoteRow as ParsedNoteRow
from app.parsing.notes import normalize_time, validate_notes
from app.schemas.notes import NoteRow, ParsedNotes

router = APIRouter(prefix="/api", tags=["notes"])


def _spot_to_parsed(spot: Spot) -> ParsedNoteRow:
    return ParsedNoteRow(
        nr=spot.nr,
        start_time=spot.start_time,
        stop_time=spot.stop_time,
        gps=spot.gps,
        light_dark=spot.light_dark,
        location=spot.location_desc,
    )


def _to_response(rows: list[ParsedNoteRow]) -> ParsedNotes:
    validate_notes(rows)  # recompute flags in place
    return ParsedNotes(
        # TODO: LLM parse_failed fallback (seminar 6) — the deterministic path
        # always succeeds, so parse_failed is False for now.
        parse_failed=False,
        rows=[
            NoteRow(
                nr=r.nr,
                start_time=r.start_time,
                stop_time=r.stop_time,
                gps=r.gps,
                light_dark=r.light_dark,
                location=r.location,
                flags=r.flags,
            )
            for r in rows
        ],
    )


@router.get("/analyses/{analysis_id}/notes", response_model=ParsedNotes)
def get_notes(analysis_id: str, session: Session = Depends(get_session)) -> ParsedNotes:
    analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        raise api_error(404, "not_found", f"Analysis {analysis_id} not found.")
    spots = sorted(analysis.spots, key=lambda s: s.nr)
    return _to_response([_spot_to_parsed(s) for s in spots])


@router.put("/analyses/{analysis_id}/notes", response_model=ParsedNotes)
def put_notes(
    analysis_id: str,
    rows: list[NoteRow],
    session: Session = Depends(get_session),
) -> ParsedNotes:
    analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        raise api_error(404, "not_found", f"Analysis {analysis_id} not found.")

    # Remember each spot's manually-picked fit window, keyed by its identity
    # (nr + window times), so re-confirming notes — e.g. after adding a pressure
    # file later — does NOT wipe a manual window whose row is unchanged. Only the
    # results should change then. If a row's times change, the offset would point
    # somewhere else, so it is intentionally dropped for that spot.
    prior_offsets = {
        (s.nr, s.start_time, s.stop_time): (s.manual_offset_s, s.manual_end_offset_s)
        for s in analysis.spots
    }

    # Replace the spot set with the confirmed rows (handles added/deleted rows).
    for spot in list(analysis.spots):
        for reading in spot.readings:
            session.delete(reading)
        for flux in spot.flux_results:
            session.delete(flux)
        session.delete(spot)

    # Normalise hand-edited times ("9:41", "09.47") to HH:MM:SS on the way in;
    # an unparseable time becomes "" and skips just that spot at match time.
    parsed = [
        ParsedNoteRow(
            nr=r.nr,
            start_time=normalize_time(r.start_time),
            stop_time=normalize_time(r.stop_time),
            gps=r.gps,
            light_dark=r.light_dark,
            location=r.location,
        )
        for r in rows
    ]
    for r in parsed:
        prior_off, prior_end = prior_offsets.get(
            (r.nr, r.start_time, r.stop_time), (None, None)
        )
        session.add(
            Spot(
                analysis_id=analysis_id,
                nr=r.nr,
                gps=r.gps,
                light_dark=r.light_dark,
                location_desc=r.location,
                start_time=r.start_time,
                stop_time=r.stop_time,
                manual_offset_s=prior_off,
                manual_end_offset_s=prior_end,
            )
        )
    session.commit()
    return _to_response(parsed)
