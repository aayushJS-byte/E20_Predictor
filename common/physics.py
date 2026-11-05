"""Sourced phase-separation physics shared by the simulator, models and tests."""

from __future__ import annotations

import numpy as np

from common.config import constants, value


def _poly(coefs, e):
    c0, c1, c2 = coefs
    return c0 * e**2 + c1 * e + c2


def water_tolerance_wt_pct(temp_c, ethanol_vol_pct=20.0):
    """Water tolerance (wt % of blend) vs fuel temperature.

    Correlation from US 8,268,629 B2 col. 10 (see constants.yaml
    water_tolerance.correlation). Returns wt % water at which a second phase
    forms.
    """
    corr = constants()["water_tolerance"]["correlation"]
    t = np.asarray(temp_c, dtype=float)
    a = _poly(corr["a"], ethanol_vol_pct)
    b = _poly(corr["b"], ethanol_vol_pct)
    c = _poly(corr["c"], ethanol_vol_pct)
    return a * t**2 + b * t + c


def tolerance_kg(temp_c, fuel_mass_kg, ethanol_vol_pct=20.0):
    """Dissolved-water capacity in kg for a given fuel mass."""
    w = water_tolerance_wt_pct(temp_c, ethanol_vol_pct) / 100.0
    # wt % is of the total (fuel + water) mass: m_w / (m_f + m_w) = w
    return fuel_mass_kg * w / (1.0 - w)


def saturation_vapour_pressure_pa(temp_c):
    m = value("physical", "magnus")
    t = np.asarray(temp_c, dtype=float)
    return 100.0 * m["A_hPa"] * np.exp(m["B"] * t / (m["C_degC"] + t))


def vapour_density_kg_m3(temp_c, rh_pct):
    """Water vapour mass concentration of air (ideal gas)."""
    r = value("physical", "gas_constant")
    mw = value("physical", "molar_mass_water")
    pv = saturation_vapour_pressure_pa(temp_c) * np.asarray(rh_pct) / 100.0
    return pv * mw / (r * (np.asarray(temp_c) + 273.15))


def pct_vv_to_mg_per_kg(pct_vv, fuel_density=None):
    """Convert water % v/v in fuel to mg/kg (approximate, densities from config)."""
    rho_w = value("physical", "density_water")
    rho_f = fuel_density or value("physical", "density_e20")
    return pct_vv / 100.0 * rho_w / rho_f * 1e6
