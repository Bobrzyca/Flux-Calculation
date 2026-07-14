"""LI-7810 parser: column set, nan preservation, and format detection."""

from pathlib import Path

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
