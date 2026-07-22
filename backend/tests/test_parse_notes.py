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


def test_real_tab_delimited_polish_headers(tmp_path: Path) -> None:
    # The real field-notes export: TAB-delimited, Polish headers, a "Gdzie"
    # (where) location column, an extra "Woda" column we ignore, and a "Light/dark"
    # column with full "Light"/"Dark" values.
    f = tmp_path / "notes.csv"
    f.write_text(
        "Nr\tnumery\tStart\tStop\tGPS\tLight/dark\tWoda\tGdzie\n"
        "1\t1\t9.38\t9.44\t770\tLight\tTak\tPow tamy staw blisko\n"
        "2\t2.\t9.45\t9.51\t809\tDark\tTak\tTroche dalej\n"
        "4\t4.\t10.04\t10.10\t?\tLight\t\tNa tamie\n",
        encoding="utf-8",
    )
    rows = validate_notes(parse_notes(f))
    assert [r.nr for r in rows] == [1, 2, 4]
    assert rows[0].start_time == "09:38:00"
    assert rows[0].stop_time == "09:44:00"
    assert [r.light_dark for r in rows] == ["light", "dark", "light"]
    assert rows[0].location == "Pow tamy staw blisko"  # from the "Gdzie" column
    assert GPS_MISSING in rows[2].flags  # GPS "?" is missing


def test_semicolon_polish_headers_and_unique_nr(tmp_path: Path) -> None:
    # The real export: semicolon-delimited, headers fid;Punkt;Start;End;Chamber,
    # CRLF line endings. Punkt->nr, End->stop, Chamber->light/dark. The "4"/"4.5"
    # pair collides on nr, so spots are renumbered 1..N to stay unique.
    f = tmp_path / "notes.csv"
    f.write_text(
        "fid;Punkt;Start;End;Chamber\r\n"
        "1;1;09:38:00;09:44:00;Light\r\n"
        "2;2;09:45:00;09:51:00;Light\r\n"
        "3;4;10:04:00;10:10:00;Light\r\n"
        "4;4.5;10:11:00;10:17:00;Dark\r\n",
        encoding="utf-8",
    )
    rows = validate_notes(parse_notes(f))
    assert [r.nr for r in rows] == [1, 2, 3, 4]  # unique, renumbered
    assert rows[0].start_time == "09:38:00"
    assert rows[0].stop_time == "09:44:00"
    assert [r.light_dark for r in rows] == ["light", "light", "light", "dark"]


# The real 2025-09-15 export: verbose English headers with a `Date` and
# `Type Of Measurement` column we ignore, `Start`/`End` times, `Light or Dark`,
# a numeric `GPS` plot id, `TEMPERATURA`, and `Other site Info` as the location.
_VERBOSE_HEADER = [
    "Nr",
    "Date",
    "Start",
    "End",
    "Type Of Measurement",
    "Light or Dark",
    "GPS",
    "TEMPERATURA",
    "Other site Info",
]
_VERBOSE_ROWS = [
    ["1", "15.09.2025", "12:18", "12:24", "Water", "Light", "764", "18.5", "nad tamą"],
    ["2", "15.09.2025", "13:03", "13:09", "Water", "Dark", "764", "18.5", "nad tamą"],
]


def _write_aligned(path: Path, sep: str) -> None:
    lines = [sep.join(row) for row in [_VERBOSE_HEADER, *_VERBOSE_ROWS]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_real_english_verbose_headers_tab(tmp_path: Path) -> None:
    # Columns must be found by keyword, not by exact alias.
    f = tmp_path / "notes.txt"
    _write_aligned(f, "\t")
    rows = validate_notes(parse_notes(f))
    assert [r.nr for r in rows] == [1, 2]
    assert rows[0].start_time == "12:18:00"
    assert rows[0].stop_time == "12:24:00"
    assert [r.light_dark for r in rows] == ["light", "dark"]
    assert rows[0].gps == "764"  # not the TEMPERATURA value
    assert rows[0].location == "nad tamą"  # from "Other site Info"
    assert rows[0].flags == []  # complete row: no missing gps/location/time issue


def test_real_english_verbose_headers_space_aligned(tmp_path: Path) -> None:
    # Same export saved space-aligned (columns separated by 4 spaces); verbose
    # headers and the "nad tamą" value keep their single internal spaces.
    f = tmp_path / "notes.txt"
    _write_aligned(f, "    ")
    rows = validate_notes(parse_notes(f))
    assert [r.nr for r in rows] == [1, 2]
    assert rows[0].start_time == "12:18:00"
    assert [r.light_dark for r in rows] == ["light", "dark"]
    assert rows[0].gps == "764"
    assert rows[0].location == "nad tamą"


def test_real_notes_cp1250_encoding(tmp_path: Path) -> None:
    # A Windows export saved in cp1250 (not UTF-8): the site name "nad tamą"
    # carries byte 0xb9 ('ą'), which used to raise UnicodeDecodeError and reject
    # the whole file. It must parse, with the accented text preserved.
    f = tmp_path / "notes.txt"
    f.write_bytes(
        ("\t".join(_VERBOSE_HEADER) + "\n" + "\t".join(_VERBOSE_ROWS[0]) + "\n").encode(
            "cp1250"
        )
    )
    rows = parse_notes(f)
    assert rows[0].start_time == "12:18:00"
    assert rows[0].light_dark == "light"
    assert rows[0].location == "nad tamą"


def test_type_of_measurement_not_mistaken_for_light_dark() -> None:
    from app.parsing.notes import _resolve_columns

    resolved = _resolve_columns(_VERBOSE_HEADER)
    assert resolved["light_dark"] == "Light or Dark"  # not "Type Of Measurement"
    assert resolved["location"] == "Other site Info"
    assert resolved["start"] == "Start"
    assert resolved["stop"] == "End"
    assert resolved["gps"] == "GPS"
    assert "Type Of Measurement" not in resolved.values()
    assert "Date" not in resolved.values()


def test_header_resolution_handles_newlines_and_comment() -> None:
    # A Word table wraps the header cell as "Light\n/dark" (internal newline);
    # it must still resolve, and a "comment" column maps to location.
    from app.parsing.notes import _resolve_columns

    headers = ["Nr", "Start", "Stop", "Light\n/dark", "comment"]
    resolved = _resolve_columns(headers)
    assert resolved["light_dark"] == "Light\n/dark"
    assert resolved["location"] == "comment"
    assert resolved["nr"] == "Nr"
