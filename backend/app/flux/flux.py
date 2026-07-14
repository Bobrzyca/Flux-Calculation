"""Closed-chamber flux formula + full unit ladder (pure; no LLM ever).

From a fitted concentration slope and the chamber constants + ambient
temperature/pressure, compute the flux in µmol·m⁻²·s⁻¹ and derive every unit on
the ladder. The core relation (ideal gas law applied to the chamber headspace):

    F [µmol·m⁻²·s⁻¹] = (dC/dt)[ppm·s⁻¹] · (P·V) / (R·T·A)

with P in Pa, V in m³, A in m², T in K. A ppm (µmol·mol⁻¹) slope times the moles
of air per m² of chamber footprint, (P·V)/(R·T·A), yields µmol·m⁻²·s⁻¹.

METHOD-OF-RECORD: the R script in ``reference/`` (not in the repo yet). This
implementation follows ``project-brief.md``; the ladder numbers are locked by
hand-computed expected values in ``tests/test_flux.py``.
TODO: re-validate against the R reference on the 2026-07-02 Kampinos campaign
once ``reference/`` lands, and reconcile any disagreement.
"""

from dataclasses import dataclass

from app.flux import constants as C


@dataclass
class FluxLadder:
    """Flux for one gas expressed across the full unit ladder.

    Field names match the frontend ``FluxLadder`` type (no ``flux_`` prefix); the
    DB ``FluxResult`` columns add that prefix when persisting.
    """

    umol_m2_s: float
    umol_m2_h: float
    mol_m2_h: float
    gC_m2_day: float
    kg_m2_h: float
    kg_ha_h: float
    kg_ha_day: float
    kg_ha_year: float
    Mg_ha_year: float
    Mg_ha_year_co2equiv: float


def compute_flux(
    slope: float,
    area_m2: float,
    volume_l: float,
    temp_c: float,
    pressure_hpa: float,
    gas: str,
) -> FluxLadder:
    """Compute the flux ladder for one gas from its fitted slope + conditions.

    ``slope`` is ppm·s⁻¹ for CO₂ and **ppb·s⁻¹ for CH₄** (converted here).
    """
    gas = gas.upper()
    if gas not in C.MOLAR_MASS_G:
        raise ValueError(f"Unknown gas {gas!r}; expected 'CO2' or 'CH4'")

    # CH₄ is measured in ppb; the flux math wants ppm·s⁻¹.
    slope_ppm_s = slope * C.CH4_PPB_TO_PPM if gas == "CH4" else slope

    pressure_pa = pressure_hpa * 100.0
    volume_m3 = volume_l / 1000.0
    temp_k = temp_c + 273.15
    # Moles of air per m² of chamber footprint (ideal gas law).
    mol_air_per_m2 = (pressure_pa * volume_m3) / (C.R_GAS * temp_k * area_m2)

    umol_m2_s = slope_ppm_s * mol_air_per_m2
    umol_m2_h = umol_m2_s * 3600.0
    mol_m2_h = umol_m2_h * 1e-6
    # Carbon mass: one C atom per molecule for both CO₂ and CH₄.
    gc_m2_day = mol_m2_h * 24.0 * C.MOLAR_MASS_C
    # Whole-molecule mass.
    kg_m2_h = mol_m2_h * C.MOLAR_MASS_G[gas] / 1000.0
    kg_ha_h = kg_m2_h * 1e4  # 1 ha = 10⁴ m²
    kg_ha_day = kg_ha_h * 24.0
    kg_ha_year = kg_ha_day * 365.0
    mg_ha_year = kg_ha_year / 1000.0  # 1 Mg (tonne) = 10³ kg
    mg_ha_year_co2eq = mg_ha_year * C.GWP_100YR[gas]

    return FluxLadder(
        umol_m2_s=umol_m2_s,
        umol_m2_h=umol_m2_h,
        mol_m2_h=mol_m2_h,
        gC_m2_day=gc_m2_day,
        kg_m2_h=kg_m2_h,
        kg_ha_h=kg_ha_h,
        kg_ha_day=kg_ha_day,
        kg_ha_year=kg_ha_year,
        Mg_ha_year=mg_ha_year,
        Mg_ha_year_co2equiv=mg_ha_year_co2eq,
    )
