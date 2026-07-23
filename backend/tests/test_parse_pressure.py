"""Pressure parser: sorted unix timestamps + hPa values, with unit handling."""

from pathlib import Path

from app.parsing.pressure import parse_pressure

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data" / "pressure_sample.csv"


def test_parse_pressure_sample() -> None:
    readings = parse_pressure(SAMPLE)
    assert len(readings) == 6
    # Sorted by time.
    timestamps = [r.timestamp for r in readings]
    assert timestamps == sorted(timestamps)
    # hPa values in a sane atmospheric range; datetime strings -> unix seconds.
    assert all(950 < r.pressure_hpa < 1050 for r in readings)
    assert 1_780_000_000 < timestamps[0] < 1_790_000_000


def test_unix_timestamps_and_kpa_conversion(tmp_path: Path) -> None:
    csv = tmp_path / "press.csv"
    csv.write_text(
        "time,pressure\n1782985020,101.3\n1782985080,101.4\n",
        encoding="utf-8",
    )
    readings = parse_pressure(csv, assume_unit="kPa")
    assert readings[0].timestamp == 1782985020.0
    # 101.3 kPa -> 1013 hPa.
    assert abs(readings[0].pressure_hpa - 1013.0) < 1e-6


def test_parse_pressure_european_imgw_style(tmp_path: Path) -> None:
    """A real-ish IMGW export: cp1250 encoding, ';' delimiter, comma decimals,
    Polish header 'Ciśnienie', dotted day-first date. All used to break."""
    csv = tmp_path / "imgw.csv"
    csv.write_bytes(
        "Data;Ciśnienie\n06.10.2025 09:38;1013,2\n06.10.2025 09:39;1013,4\n".encode(
            "cp1250"
        )
    )
    readings = parse_pressure(csv)
    assert len(readings) == 2
    assert all(1000 < r.pressure_hpa < 1020 for r in readings)
    assert abs(readings[0].pressure_hpa - 1013.2) < 1e-6
    # 6 October 2025 (day-first), not 10 June.
    from datetime import UTC, datetime

    assert datetime.fromtimestamp(readings[0].timestamp, tz=UTC).month == 10


def test_parse_pressure_separate_date_time_columns(tmp_path: Path) -> None:
    csv = tmp_path / "press.csv"
    csv.write_text(
        "Data;Godzina;Cisnienie\n2025-10-06;09:38:00;1012.5\n"
        "2025-10-06;09:39:00;1012.6\n",
        encoding="utf-8",
    )
    readings = parse_pressure(csv)
    assert len(readings) == 2
    assert abs(readings[0].pressure_hpa - 1012.5) < 1e-6
    assert readings[0].timestamp < readings[1].timestamp


def test_parse_pressure_tab_delimited(tmp_path: Path) -> None:
    txt = tmp_path / "press.txt"
    txt.write_text(
        "timestamp\tpressure\n2025-10-06 09:38:00\t1011.0\n",
        encoding="utf-8",
    )
    readings = parse_pressure(txt)
    assert len(readings) == 1
    assert abs(readings[0].pressure_hpa - 1011.0) < 1e-6


def test_parse_pressure_rejects_legacy_xls(tmp_path: Path) -> None:
    fake = tmp_path / "p.xls"
    fake.write_bytes(b"\xd0\xcf\x11\xe0nope")
    try:
        parse_pressure(fake)
    except ValueError as exc:
        assert ".xls" in str(exc)
    else:
        raise AssertionError("expected ValueError for legacy .xls")
