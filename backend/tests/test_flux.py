"""Flux math: ladder locked to hand-computed values + gas conversions.

The expected ladder below is frozen for a known input (slope 2.0 ppm/s, chamber
0.0625 m² / 15.625 L, 20 °C, 1013.25 hPa, CO₂). The anchor umol_m2_s was checked
by hand: (P·V)/(R·T·A)·slope = (101325·0.015625)/(8.314462618·293.15·0.0625)·2.0
≈ 20.7856. TODO: re-validate against the R reference when reference/ lands.
"""

import pytest

from app.flux import constants as C
from app.flux.flux import compute_flux

ANCHOR = {
    "umol_m2_s": 20.785598456300225,
    "umol_m2_h": 74828.15444268081,
    "mol_m2_h": 0.0748281544426808,
    "gC_m2_day": 21.570263112264936,
    "kg_m2_h": 0.003293149662945161,
    "kg_ha_h": 32.93149662945161,
    "kg_ha_day": 790.3559191068387,
    "kg_ha_year": 288479.91047399613,
    "Mg_ha_year": 288.47991047399614,
    "Mg_ha_year_co2equiv": 288.47991047399614,
}


def test_ladder_matches_hand_computed_values() -> None:
    ladder = compute_flux(2.0, 0.0625, 15.625, 20.0, 1013.25, "CO2")
    for unit, expected in ANCHOR.items():
        assert getattr(ladder, unit) == pytest.approx(expected, rel=1e-12), unit


def test_ladder_internal_ratios() -> None:
    ladder = compute_flux(2.0, 0.0625, 15.625, 20.0, 1013.25, "CO2")
    assert ladder.umol_m2_h == pytest.approx(ladder.umol_m2_s * 3600.0)
    assert ladder.mol_m2_h == pytest.approx(ladder.umol_m2_h * 1e-6)
    assert ladder.kg_ha_h == pytest.approx(ladder.kg_m2_h * 1e4)
    assert ladder.kg_ha_year == pytest.approx(ladder.kg_ha_day * 365.0)
    assert ladder.Mg_ha_year == pytest.approx(ladder.kg_ha_year / 1000.0)


def test_ch4_ppb_to_ppm_conversion() -> None:
    # Same numeric slope: CH₄ (ppb) yields flux 1000× smaller than CO₂ (ppm),
    # before any GWP weighting.
    co2 = compute_flux(2.0, 0.0625, 15.625, 20.0, 1013.25, "CO2")
    ch4 = compute_flux(2.0, 0.0625, 15.625, 20.0, 1013.25, "CH4")
    assert co2.umol_m2_s == pytest.approx(ch4.umol_m2_s * 1000.0)


def test_co2_equivalent_uses_gwp() -> None:
    co2 = compute_flux(2.0, 0.0625, 15.625, 20.0, 1013.25, "CO2")
    ch4 = compute_flux(2.0, 0.0625, 15.625, 20.0, 1013.25, "CH4")
    # CO₂ equivalent == the gas's own mass × its GWP.
    assert co2.Mg_ha_year_co2equiv == pytest.approx(co2.Mg_ha_year)
    assert ch4.Mg_ha_year_co2equiv == pytest.approx(ch4.Mg_ha_year * C.GWP_100YR["CH4"])


def test_unknown_gas_raises() -> None:
    with pytest.raises(ValueError):
        compute_flux(1.0, 0.0625, 15.625, 20.0, 1013.25, "N2O")
