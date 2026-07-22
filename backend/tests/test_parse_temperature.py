"""Temperature parser: columns, monotonic timestamps, numeric values."""

from pathlib import Path

import pytest

from app.parsing.temperature import parse_temperature

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
SAMPLE = SAMPLE_DIR / "temperature_sample.xlsx"


def test_parse_temperature_shape_and_order() -> None:
    df = parse_temperature(SAMPLE)
    assert list(df.columns) == ["timestamp", "temperature_c"]
    assert len(df) > 1
    # Sorted by time and every temperature is a real number.
    assert df["timestamp"].is_monotonic_increasing
    assert df["temperature_c"].notna().all()


def test_timestamps_are_unix_seconds() -> None:
    df = parse_temperature(SAMPLE)
    # 2026-07-02 morning -> ~1.78e9 unix seconds; spacing ~30 s.
    assert 1_780_000_000 < df["timestamp"].iloc[0] < 1_790_000_000
    diffs = df["timestamp"].diff().dropna()
    assert (diffs == 30.0).all()


def test_parse_temperature_reads_csv(tmp_path: Path) -> None:
    # Temperature logs also arrive as CSV; column names vary in case/spelling.
    f = tmp_path / "temp.csv"
    f.write_text(
        "Time,Temperature\n2026-07-02 08:00:00,18.2\n2026-07-02 08:00:30,18.4\n",
        encoding="utf-8",
    )
    df = parse_temperature(f)
    assert list(df.columns) == ["timestamp", "temperature_c"]
    assert df["temperature_c"].tolist() == [18.2, 18.4]
    assert df["timestamp"].diff().dropna().iloc[0] == 30.0


def test_parse_temperature_real_tab_delimited_format(tmp_path: Path) -> None:
    # The real logger export: TAB-delimited, day-first dotted dates, a
    # `Temp(°C)` column, plus columns we ignore (Status, Type, CO2, RH).
    from datetime import UTC, datetime

    f = tmp_path / "temp.txt"
    f.write_text(
        "Date\tStatus\tType\tCO2(ppm)\tTemp(°C)\tRH(%)\n"
        "02.07.2026 09:15\t0x00\tData\t295\t24.38\t58.02\n"
        "02.07.2026 09:16\t0x00\tData\t100\t23.86\t58.45\n",
        encoding="utf-8",
    )
    df = parse_temperature(f)
    assert list(df.columns) == ["timestamp", "temperature_c"]
    assert df["temperature_c"].tolist() == [24.38, 23.86]
    # Day-first: 02.07.2026 is 2 July (not 7 Feb); stored as naive-UTC wall-clock
    # so it aligns with the local-time notes.
    expected = datetime(2026, 7, 2, 9, 15, tzinfo=UTC).timestamp()
    assert df["timestamp"].iloc[0] == expected
    assert df["timestamp"].diff().dropna().iloc[0] == 60.0


def test_parse_temperature_iso_datetime_not_flipped(tmp_path: Path) -> None:
    # The real 2025-10-06 logger export: TAB-delimited, a single `Date` column
    # holding an ISO `YYYY-MM-DD HH:MM:SS` datetime, plus columns we ignore.
    # Parsing it day-first would flip 2025-10-06 to 10 June and it would never
    # line up with the concentration record — so ISO dates must stay year-first.
    from datetime import UTC, datetime

    f = tmp_path / "temp.txt"
    f.write_text(
        "Date\tStatus\tType\tCO2(ppm)\tTemp(°C)\tRH(%)\n"
        "2025-10-06 09:22:20\t0x00\tData\t417\t13.35\t93.25\n"
        "2025-10-06 09:22:50\t0x00\tData\t420\t13.48\t94.33\n",
        encoding="utf-8",
    )
    df = parse_temperature(f)
    assert df["temperature_c"].tolist() == [13.35, 13.48]
    expected = datetime(2025, 10, 6, 9, 22, 20, tzinfo=UTC).timestamp()
    assert df["timestamp"].iloc[0] == expected
    assert df["timestamp"].diff().dropna().iloc[0] == 30.0


def test_parse_temperature_space_aligned_columns(tmp_path: Path) -> None:
    # Some loggers export space-aligned (fixed-width-ish) columns rather than
    # tab/comma. Columns are separated by runs of 2+ spaces, while the datetime
    # keeps its single internal space — so the date must not get split off.
    from datetime import UTC, datetime

    f = tmp_path / "temp.txt"
    f.write_text(
        "Date                   Status    Type      CO2(ppm)    Temp(°C)    RH(%)\n"
        "2025-10-06 09:22:20    0x00      Data      417         13.35       93.25\n"
        "2025-10-06 09:22:50    0x00      Data      420         13.48       94.33\n",
        encoding="utf-8",
    )
    df = parse_temperature(f)
    assert df["temperature_c"].tolist() == [13.35, 13.48]
    expected = datetime(2025, 10, 6, 9, 22, 20, tzinfo=UTC).timestamp()
    assert df["timestamp"].iloc[0] == expected


def test_parse_temperature_separate_date_and_time_columns(tmp_path: Path) -> None:
    # Date and time in TWO separate columns (ISO date). They must be combined,
    # not have one silently ignored.
    from datetime import UTC, datetime

    f = tmp_path / "temp.csv"
    f.write_text(
        "Date\tTime\tTemp(°C)\tRH(%)\n"
        "2025-10-06\t09:22:20\t13.35\t93.25\n"
        "2025-10-06\t09:22:50\t13.48\t94.33\n",
        encoding="utf-8",
    )
    df = parse_temperature(f)
    assert df["temperature_c"].tolist() == [13.35, 13.48]
    assert (
        df["timestamp"].iloc[0]
        == datetime(2025, 10, 6, 9, 22, 20, tzinfo=UTC).timestamp()
    )
    assert df["timestamp"].diff().dropna().iloc[0] == 30.0


def test_parse_temperature_separate_polish_columns_dotted(tmp_path: Path) -> None:
    # Polish headers with a separate day-first dotted Data + Godzina.
    from datetime import UTC, datetime

    f = tmp_path / "temp.csv"
    f.write_text(
        "Data;Godzina;Temperatura\n"
        "06.10.2025;09:22:20;13.35\n"
        "06.10.2025;09:22:50;13.48\n",
        encoding="utf-8",
    )
    df = parse_temperature(f)
    assert df["temperature_c"].tolist() == [13.35, 13.48]
    # 06.10.2025 is 6 October (day-first), not 10 June.
    assert (
        df["timestamp"].iloc[0]
        == datetime(2025, 10, 6, 9, 22, 20, tzinfo=UTC).timestamp()
    )


def test_parse_temperature_dayfirst_inferred_from_values(tmp_path: Path) -> None:
    # A leading component > 12 proves the day comes first even though the file is
    # dotted; 13.10.2025 can only be 13 October.
    from datetime import UTC, datetime

    f = tmp_path / "temp.csv"
    f.write_text(
        "Date,Temp\n13.10.2025 09:00,10.0\n13.10.2025 09:01,10.1\n",
        encoding="utf-8",
    )
    df = parse_temperature(f)
    assert (
        df["timestamp"].iloc[0] == datetime(2025, 10, 13, 9, 0, tzinfo=UTC).timestamp()
    )


def test_parse_temperature_us_month_first_inferred(tmp_path: Path) -> None:
    # A second component > 12 proves month-first (US MM/DD/YYYY): 10/13/2025 is
    # 13 October, so the parser must NOT read it day-first.
    from datetime import UTC, datetime

    f = tmp_path / "temp.csv"
    f.write_text(
        "Date,Temp\n10/13/2025 09:00,10.0\n10/13/2025 09:01,10.1\n",
        encoding="utf-8",
    )
    df = parse_temperature(f)
    assert (
        df["timestamp"].iloc[0] == datetime(2025, 10, 13, 9, 0, tzinfo=UTC).timestamp()
    )


def test_parse_temperature_unfamiliar_headers_content_fallback(tmp_path: Path) -> None:
    # Headers we don't recognise by name: fall back to the column whose values
    # actually parse as datetimes, and to the °C column for temperature.
    from datetime import UTC, datetime

    f = tmp_path / "temp.csv"
    f.write_text(
        "idx,Znacznik,Odczyt [°C]\n"
        "1,2025-10-06 09:22:20,13.35\n"
        "2,2025-10-06 09:22:50,13.48\n",
        encoding="utf-8",
    )
    df = parse_temperature(f)
    assert df["temperature_c"].tolist() == [13.35, 13.48]
    assert (
        df["timestamp"].iloc[0]
        == datetime(2025, 10, 6, 9, 22, 20, tzinfo=UTC).timestamp()
    )


def test_parse_temperature_separate_columns_xlsx(tmp_path: Path) -> None:
    # Excel with a date-only Date column (round-trips to midnight) and a separate
    # Time column: the midnight tail must be stripped and the real time attached.
    from datetime import UTC, datetime
    from datetime import time as dtime

    import openpyxl

    f = tmp_path / "temp.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Date", "Time", "Temp"])
    ws.append([datetime(2025, 10, 6), dtime(9, 22, 20), 13.35])
    ws.append([datetime(2025, 10, 6), dtime(9, 22, 50), 13.48])
    wb.save(f)
    df = parse_temperature(f)
    assert df["temperature_c"].tolist() == [13.35, 13.48]
    assert (
        df["timestamp"].iloc[0]
        == datetime(2025, 10, 6, 9, 22, 20, tzinfo=UTC).timestamp()
    )


def test_parse_temperature_bad_file_raises_valueerror(tmp_path: Path) -> None:
    # A file that is neither a readable spreadsheet nor a parseable table
    # raises a clear ValueError (the API turns this into a 422, not a 500).
    f = tmp_path / "broken.xlsx"
    f.write_bytes(b"this is not a real xlsx file")
    with pytest.raises(ValueError):
        parse_temperature(f)
