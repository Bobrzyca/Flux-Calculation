"""LI-7810 parser: column set, nan preservation, and format detection."""

from datetime import date
from pathlib import Path

from app.matching.match import note_time_to_unix
from app.parsing.li7810 import looks_like_li7810, parse_li7810

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
LI7810 = SAMPLE_DIR / "li7810_sample.txt"
TEMPERATURE = SAMPLE_DIR / "temperature_sample.xlsx"


def test_parse_returns_expected_columns_and_types() -> None:
    df = parse_li7810(LI7810)
    assert list(df.columns) == ["timestamp", "co2_ppm", "ch4_ppb"]
    assert len(df) > 100
    # Timestamps are always present and monotonic (1 Hz stream).
    assert df["timestamp"].notna().all()
    assert df["timestamp"].is_monotonic_increasing


def test_nans_are_preserved_not_dropped() -> None:
    df = parse_li7810(LI7810)
    # Warm-up block + mid-stream dropouts survive as nan (dropping is later).
    assert df["co2_ppm"].isna().any()
    assert df["ch4_ppb"].isna().any()
    # The first row is warm-up (nan) but still has a timestamp.
    assert df["co2_ppm"].isna().iloc[0]


def test_looks_like_li7810_accepts_sample() -> None:
    assert looks_like_li7810(LI7810) is True


def test_looks_like_li7810_rejects_bogus_files(tmp_path: Path) -> None:
    # The temperature xlsx is binary -> not a LI-7810 text export.
    assert looks_like_li7810(TEMPERATURE) is False

    random_csv = tmp_path / "random.csv"
    random_csv.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    assert looks_like_li7810(random_csv) is False

    missing = tmp_path / "does_not_exist.txt"
    assert looks_like_li7810(missing) is False


# A realistic LI-7810 export: a multi-line metadata preamble, then LI-COR's
# DATAH (column names) / DATAU (units) / DATA (row) markers — the header is NOT
# on the second line, and there's a units row before the numbers.
_REALISTIC_LI7810 = (
    "Model:\tLI-7810\n"
    "SN:\tTG10-01234\n"
    "Instrument:\tLI-7810\n"
    "Software Version:\t1.2.3\n"
    "TimeZone:\tUTC\n"
    "System Name:\tKampinos\n"
    "\n"
    "DATAH\tSECONDS\tNANOSECONDS\tDIAG\tREMARK\tCO2\tCH4\tH2O\tCAVITY_T\n"
    "DATAU\tseconds\tnanoseconds\t\t\tppm\tppb\tppm\tC\n"
    "DATA\t1782985020\t0\t0\t\tnan\tnan\tnan\t18.20\n"
    "DATA\t1782985021\t0\t0\t\t421.3\t1998.4\t12000\t18.21\n"
    "DATA\t1782985022\t0\t0\t\t421.5\t1999.1\t12010\t18.22\n"
)


def test_looks_like_li7810_accepts_multiline_preamble(tmp_path: Path) -> None:
    f = tmp_path / "real.data"
    f.write_text(_REALISTIC_LI7810, encoding="utf-8")
    assert looks_like_li7810(f) is True


def test_parse_handles_multiline_preamble_and_units_row(tmp_path: Path) -> None:
    f = tmp_path / "real.data"
    f.write_text(_REALISTIC_LI7810, encoding="utf-8")
    df = parse_li7810(f)
    assert list(df.columns) == ["timestamp", "co2_ppm", "ch4_ppb"]
    # Three DATA rows; the DATAU units row is dropped (no usable timestamp).
    assert len(df) == 3
    assert df["timestamp"].notna().all()
    assert df["timestamp"].iloc[0] == 1782985020
    # Warm-up nan preserved; real values parsed as floats.
    assert df["co2_ppm"].isna().iloc[0]
    assert df["co2_ppm"].iloc[1] == 421.3
    assert df["ch4_ppb"].iloc[2] == 1999.1


# A real LI-7810 export: DATAH/DATAU/DATA markers and separate DATE + TIME
# columns holding **local** wall-clock. SECONDS is true unix (a different tz),
# so the parser must build the timeline from DATE+TIME to align with the
# local-time field notes.
_REAL_LICOR = (
    "Model:\tLI-7810\n"
    "SN:\tTG10-02218\n"
    "Timestamp:\t2026-07-02 09:11:00\n"
    "Timezone:\tEurope/Warsaw\n"
    "DATAH\tSECONDS\tNANOSECONDS\tDIAG\tREMARK\tDATE\tTIME\tH2O\tCO2\tCH4\tCAVITY_T\n"
    "DATAU\tsecs\tnsecs\tdiag\t\tdate\ttime\tppm\tppm\tppb\tC\n"
    "DATA\t1782976260\t0\t256\t\t2026-07-02\t09:11:00\tnan\tnan\tnan\t33.0\n"
    "DATA\t1782976261\t0\t256\t\t2026-07-02\t09:11:01\t12000\t420.5\t1990.1\t33.0\n"
    "DATA\t1782976262\t0\t256\t\t2026-07-02\t09:11:02\t12010\t421.0\t1991.0\t33.0\n"
)


def test_parse_uses_local_date_time_not_unix_seconds(tmp_path: Path) -> None:
    f = tmp_path / "real.data"
    f.write_text(_REAL_LICOR, encoding="utf-8")
    assert looks_like_li7810(f) is True
    df = parse_li7810(f)
    assert list(df.columns) == ["timestamp", "co2_ppm", "ch4_ppb"]
    assert len(df) == 3  # DATAU units row dropped
    # Timeline comes from DATE+TIME (local wall-clock), NOT the true-unix SECONDS
    # column — so it lines up with the notes, which are local wall-clock too.
    assert df["timestamp"].iloc[0] == note_time_to_unix(date(2026, 7, 2), "09:11:00")
    assert df["timestamp"].iloc[0] != 1782976260  # would be the raw SECONDS
    assert df["co2_ppm"].isna().iloc[0]  # warm-up
    assert df["co2_ppm"].iloc[1] == 420.5
    assert df["ch4_ppb"].iloc[2] == 1991.0


def test_parse_is_case_insensitive_on_columns(tmp_path: Path) -> None:
    f = tmp_path / "lower.txt"
    f.write_text(
        "Model:\tLI-7810\n"
        "extra metadata line\n"
        "seconds\tco2\tch4\ttemp\n"
        "1782985020\t420.1\t1990.0\t18.2\n",
        encoding="utf-8",
    )
    assert looks_like_li7810(f) is True
    df = parse_li7810(f)
    assert df["co2_ppm"].iloc[0] == 420.1
    assert df["ch4_ppb"].iloc[0] == 1990.0


def test_high_co2_spikes_dropped(tmp_path: Path) -> None:
    # CO2 >= 1500 ppm are sensor spikes and are dropped (nan), like the R script.
    f = tmp_path / "hi.txt"
    f.write_text(
        "Model:\tLI-7810\n"
        "SECONDS\tCO2\tCH4\n"
        "1782985020\t420.0\t1990.0\n"
        "1782985021\t99999.0\t1991.0\n"
        "1782985022\t421.0\t1992.0\n",
        encoding="utf-8",
    )
    df = parse_li7810(f)
    assert df["co2_ppm"].isna().iloc[1]  # the 99999 spike -> nan
    assert df["co2_ppm"].iloc[0] == 420.0
    assert df["ch4_ppb"].iloc[1] == 1991.0  # CH4 untouched


def test_gross_negative_co2_dropped(tmp_path: Path) -> None:
    # CO2 < -1500 ppm are gross sensor faults / error sentinels -> dropped (nan).
    f = tmp_path / "lo.txt"
    f.write_text(
        "Model:\tLI-7810\n"
        "SECONDS\tCO2\tCH4\n"
        "1782985020\t420.0\t1990.0\n"
        "1782985021\t-9999.0\t1991.0\n"
        "1782985022\t421.0\t1992.0\n",
        encoding="utf-8",
    )
    df = parse_li7810(f)
    assert df["co2_ppm"].isna().iloc[1]  # the -9999 fault -> nan
    assert df["co2_ppm"].iloc[0] == 420.0
    assert df["ch4_ppb"].iloc[1] == 1991.0  # CH4 untouched
