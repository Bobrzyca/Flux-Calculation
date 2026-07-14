"""Notes parser + validation: time normalisation and per-row flags."""

from pathlib import Path

from docx import Document

from app.parsing.notes import (
    GPS_MISSING,
    LOCATION_MISSING,
    STOP_BEFORE_START,
    UNPARSEABLE_TIME,
    parse_notes,
    validate_notes,
)

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data" / "notes_sample.csv"


def test_clean_times_normalised_to_hhmmss() -> None:
    rows = parse_notes(SAMPLE)
    by_nr = {r.nr: r for r in rows}
    # Dot and colon-without-seconds both normalise to HH:MM:SS.
    assert by_nr[1].start_time == "09:38:00"
    assert by_nr[1].stop_time == "09:44:00"
    assert by_nr[2].start_time == "09:50:00"
    assert by_nr[3].start_time == "10:10:00"
    assert by_nr[1].light_dark == "light"
    assert by_nr[2].light_dark == "dark"


def test_flags_from_validation() -> None:
    rows = validate_notes(parse_notes(SAMPLE))
    by_nr = {r.nr: r for r in rows}
    # Row 1 is clean.
    assert by_nr[1].flags == []
    # Row 2 has a blank GPS.
    assert GPS_MISSING in by_nr[2].flags
    # Row 4 stops before it starts.
    assert STOP_BEFORE_START in by_nr[4].flags


def test_unparseable_and_missing_location(tmp_path: Path) -> None:
    csv = tmp_path / "messy.csv"
    csv.write_text(
        "Nr,Start,Stop,GPS,light/dark,location\n"
        "1,13 33,13:40,52.0;20.0,light,\n",  # space-in-time (messy) + blank location
        encoding="utf-8",
    )
    rows = validate_notes(parse_notes(csv))
    assert rows[0].start_time == ""  # not repaired (LLM's job)
    assert UNPARSEABLE_TIME in rows[0].flags
    assert LOCATION_MISSING in rows[0].flags


def test_polish_headers_accepted(tmp_path: Path) -> None:
    csv = tmp_path / "polish.csv"
    csv.write_text(
        "Nr,Początek,Koniec,GPS,light/dark,lokalizacja\n"
        "1,9:00,9:06,52.0;20.0,ciemny,brzeg\n",
        encoding="utf-8",
    )
    rows = parse_notes(csv)
    assert rows[0].start_time == "09:00:00"
    assert rows[0].stop_time == "09:06:00"
    assert rows[0].light_dark == "dark"
    assert rows[0].location == "brzeg"


def test_docx_notes_table(tmp_path: Path) -> None:
    docx_path = tmp_path / "notes.docx"
    document = Document()
    table = document.add_table(rows=2, cols=6)
    header = ["Nr", "Start", "Stop", "GPS", "light/dark", "location"]
    values = ["2", "10.05", "10.11", "52.1,20.2", "light", "pond"]
    for col, text in enumerate(header):
        table.rows[0].cells[col].text = text
    for col, text in enumerate(values):
        table.rows[1].cells[col].text = text
    document.save(str(docx_path))

    rows = parse_notes(docx_path)
    assert len(rows) == 1
    assert rows[0].nr == 2
    assert rows[0].start_time == "10:05:00"
