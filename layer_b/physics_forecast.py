"""Physics baseline forecaster: roll the tank mass balance forward from observables.

Uses only what a retail outlet could observe (no simulator truth):
  * the latest dissolved-water test (mg/kg) and the ATG fuel volume -> dissolved kg
  * the ATG water-float height -> settled/lower-phase water volume -> kg
  * the last 72 h of rainfall
  * the weather forecast for the next 72 h (here: the ERA5 record itself, i.e. a
    perfect forecast — stated on the site)

Ingress model fitted on the last 7 daily water-test intervals with a robust
(median) estimator:  ingress_kg_per_day = a + b * precip_mm_per_day
(a = background rate, b = effective rain catchment in kg/mm). Then forward:
  W(t+k) = W(t) + sum(a + b * precip_fcst) ; dispensing at the trailing-24 h rate
  removes dissolved water pro rata ; margin = 1 - W / C(T_fcst, fuel mass).
The cone is +/- 2 standard errors on (a, b).
"""

from __future__ import annotations

import numpy as np

from common.config import value
from common.physics import pct_vv_to_mg_per_kg, tolerance_kg

HORIZON_H = 72
STEPS_PER_H = 2
WINDOW_DAYS = 7
RAIN_DAY_MM = 2.0


def _robust_rate(precip: np.ndarray, ingress: np.ndarray) -> tuple[float, float, float, float]:
    """Robust (median-based) fit of ingress/day = a + b * precip/day, a, b >= 0.

    a: median ingress on dry days; b: median (ingress - a) / precip on rainy
    days. Medians ignore one-off slugs (e.g. a wet tanker) that a least-squares
    rate would turn into a sustained trend. Spread from the MAD.
    """
    dry = precip < RAIN_DAY_MM
    wet = precip >= RAIN_DAY_MM
    base = ingress[dry] if dry.any() else ingress
    a = max(0.0, float(np.median(base)))
    se_a = 1.4826 * float(np.median(np.abs(base - np.median(base)))) / np.sqrt(len(base))
    b, se_b = 0.0, 0.0
    if wet.sum() >= 2:
        r = (ingress[wet] - a) / precip[wet]
        b_med = float(np.median(r))
        se = 1.4826 * float(np.median(np.abs(r - b_med))) / np.sqrt(wet.sum())
        if b_med > 2 * se:  # accept a rain catchment only with statistical support
            b, se_b = b_med, se
    return a, b, se_a, se_b


def prepare(obs: dict) -> None:
    """Precompute observed water inventories (kg) once per run.

    The float sees a bottom layer. If dissolved + layer-as-water would exceed
    the tolerance, the layer is taken to be the separated ethanol-water phase
    and only its water fraction (lower_phase.ethanol_mass_fraction) is counted.
    """
    rho_f = value("physical", "density_e20")
    rho_w = value("physical", "density_water")
    rho_e = value("physical", "density_ethanol")
    f = value("lower_phase", "ethanol_mass_fraction")
    rho_low = 1.0 / (f / rho_e + (1 - f) / rho_w)
    fuel_kg = np.asarray(obs["gauge_fuel_m3"]) * rho_f
    diss = np.asarray(obs["sensor_water_mgkg"]) * 1e-6 * fuel_kg
    vol = np.asarray(obs["gauge_lower_m3"])
    cap = tolerance_kg(np.asarray(obs["t_fuel"]), fuel_kg, 20.0)
    as_water = vol * rho_w
    separated = diss + as_water > cap
    obs["_diss"] = diss
    obs["_W"] = diss + np.where(separated, vol * rho_low * (1 - f), as_water)


def fit_ingress(obs: dict, i: int) -> tuple[float, float, float, float]:
    """Fit per-step ingress a + b*precip from the daily water tests before step i.

    Between consecutive tests k-1 -> k:
      ingress = dW + water dispensed (at the test-(k-1) concentration) - known deliveries + drained
    """
    sample = int(value("tank", "water_sample_interval_h")) * STEPS_PER_H
    ks = list(range(0, i + 1, sample))[-(WINDOW_DAYS + 1):]
    if len(ks) < 3:
        return 0.0, 0.0, 0.0, 0.0
    fuel = np.asarray(obs["gauge_fuel_m3"])
    conc = np.asarray(obs["sensor_water_mgkg"]) * 1e-6
    rho_f = value("physical", "density_e20")
    ys, xs = [], []
    for k0, k1 in zip(ks[:-1], ks[1:], strict=True):
        dV = np.diff(fuel[k0:k1 + 1])
        dispensed = float(np.sum(np.where(dV < 0, -dV, 0.0))) * rho_f * conc[k0]
        known = float(np.sum(obs["delivered_water_kg"][k0 + 1:k1 + 1]) - np.sum(obs["drained_kg"][k0 + 1:k1 + 1]))
        ys.append(obs["_W"][k1] - obs["_W"][k0] + dispensed - known)
        xs.append(float(np.sum(obs["precip_mm"][k0 + 1:k1 + 1])))
    a_day, b, se_a, se_b = _robust_rate(np.array(xs), np.array(ys))
    return a_day / sample, b, se_a / sample, se_b


def forecast(obs: dict, i: int, t_fuel_fcst: np.ndarray, precip_fcst: np.ndarray,
             ethanol_pct: float = 20.0) -> dict:
    """Margin forecast at hourly horizons 1..72 from step i.

    obs: dict of equal-length arrays (30-min steps): gauge_fuel_m3, gauge_lower_m3,
         sensor_water_mgkg, precip_mm, delivered_water_kg, drained_kg
    t_fuel_fcst, precip_fcst: next HORIZON_H*STEPS_PER_H steps.
    """
    if "_W" not in obs:
        prepare(obs)
    a, b, se_a, se_b = fit_ingress(obs, i)

    d0 = float(obs["_diss"][i])
    b0 = float(obs["_W"][i]) - d0
    v0 = float(obs["gauge_fuel_m3"][i])
    k0 = max(0, i - 48)
    rate = max(0.0, -float(np.mean(np.minimum(np.diff(obs["gauge_fuel_m3"][k0:i + 1]), 0)))) if i > 0 else 0.0
    rho_f = value("physical", "density_e20")
    n = HORIZON_H * STEPS_PER_H
    # fuel and dissolved water under the station's known reorder policy
    cap_m3 = value("tank", "capacity_m3")
    trigger = value("tank", "delivery_trigger_fraction") * cap_m3
    dvol = value("tank", "delivery_volume_m3")
    w_spec = obs.get("_w_spec_kg_per_m3")
    if w_spec is None:
        w_spec = pct_vv_to_mg_per_kg(value("spec", "e20_max_water_content")) * 1e-6 * rho_f
    V = np.empty(n)
    D = np.empty(n)
    v, d = v0, d0
    for k in range(n):
        out_v = min(rate, max(v - 1.0, 0.0))
        d -= d * out_v / v if v > 0 else 0.0
        v -= out_v
        if v < trigger:
            add = min(dvol, 0.95 * cap_m3 - v)
            v += add
            d += w_spec * add
        V[k], D[k] = v, d
    C = tolerance_kg(np.asarray(t_fuel_fcst[:n]), V * rho_f, ethanol_pct)
    pf = np.asarray(precip_fcst[:n])
    out = {"a": a, "b": b, "se_a": se_a, "se_b": se_b, "hours": list(range(1, HORIZON_H + 1))}
    for name, (aa, bb) in {"mid": (a, b), "lo": (max(0, a - 2 * se_a), max(0, b - 2 * se_b)),
                           "hi": (a + 2 * se_a, b + 2 * se_b)}.items():
        B = b0 + np.cumsum(aa + bb * pf)
        m = 1.0 - (D + B) / C
        out[name] = m[STEPS_PER_H - 1::STEPS_PER_H].tolist()
    out["time_to_separation_h"] = time_to_zero(out["mid"])
    return out


def time_to_zero(margins, hours=None) -> float | None:
    """First (interpolated) hour at which the margin reaches 0, else None."""
    hours = hours or list(range(1, len(margins) + 1))
    prev_h, prev_m = 0.0, None
    for h, m in zip(hours, margins, strict=True):
        if m <= 0:
            if prev_m is None or prev_m <= 0:
                return float(h if prev_m is None else prev_h)
            return float(prev_h + (h - prev_h) * prev_m / (prev_m - m))
        prev_h, prev_m = h, m
    return None
