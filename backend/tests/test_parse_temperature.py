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


def test_parse_temperature_bad_file_raises_valueerror(tmp_path: Path) -> None:
    # A file that is neither a readable spreadsheet nor a parseable table
    # raises a clear ValueError (the API turns this into a 422, not a 500).
    f = tmp_path / "broken.xlsx"
    f.write_bytes(b"this is not a real xlsx file")
    with pytest.raises(ValueError):
        parse_temperature(f)
