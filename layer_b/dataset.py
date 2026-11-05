"""Simulated tank fleet -> observables -> supervised forecasting table (SYNTHETIC).

Time-based split: tanks driven by 2022-2023 weather are used for training,
tanks driven by 2024 weather for testing (different seeds as well), so no
future weather or tank leaks into training.

Fleet parameters are randomised (domain randomisation) over the ASSUMPTION
ranges below so the models are not tuned to one guessed value.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from common.config import value
from common.physics import pct_vv_to_mg_per_kg, tolerance_kg
from sim.tank import STEPS_PER_DAY, Mulberry32, TankParams, segment_volume, simulate
from sim.weather import load as load_weather

HORIZONS_H = [6, 12, 24, 36, 48, 60, 72]
SAMPLE_EVERY = 12  # steps (6 h) between forecast origins
TRAIN_YEARS = ["2022", "2023"]
TEST_YEARS = ["2024"]
TANKS_PER_YEAR = 80


@dataclass
class TankRun:
    tank_id: str
    year: str
    params: TankParams
    trace: pd.DataFrame
    events: list
    ledger: dict
    obs: dict


def random_params(rng: Mulberry32, seed: int) -> TankParams:
    u = rng.random
    seal = "none" if u() < 0.45 else ("minor" if u() < 0.5 else "major")
    return TankParams(
        seal=seal,
        seal_fault_start_day=float(int(u() * 200)),
        drain_out=u() < 0.5,
        dispense_m3_per_day=2.0 + 4.0 * u(),
        wet_tanker_probability=0.05 + 0.25 * u(),
        initial_fill_fraction=0.4 + 0.4 * u(),
        dissolution_kg_per_day=1.0 + 5.0 * u(),
        moisture_capture_efficiency=0.5 + 0.5 * u(),
        seed=seed,
    )


def observables(trace: pd.DataFrame, events: list, p: TankParams) -> dict:
    """What a station could record: ATG gauges, daily water test, logs, weather."""
    radius = value("tank", "tank_diameter_m") / 2
    length = p.capacity_m3 / (np.pi * radius**2)
    n = len(trace)
    delivered = np.zeros(n)
    drained = np.zeros(n)
    w_spec = pct_vv_to_mg_per_kg(value("spec", "e20_max_water_content")) * 1e-6 * value("physical", "density_e20")
    for e in events:
        if e["type"] == "delivery":
            delivered[e["step"]] += w_spec * e["volume_m3"]   # known nominal; wet-tanker water is NOT known
        elif e["type"] == "drain_out":
            drained[e["step"]] += e["water_kg"]               # Solution 4 drain-out record
    lower_m3 = np.array([segment_volume(h / 1000.0, radius, length) for h in trace["gauge_water_mm"].to_numpy()])
    return {
        "gauge_fuel_m3": trace["gauge_fuel_m3"].to_numpy(),
        "gauge_water_mm": trace["gauge_water_mm"].to_numpy(),
        "gauge_lower_m3": lower_m3,
        "sensor_water_mgkg": trace["sensor_water_mgkg"].to_numpy(),
        "t_fuel": trace["gauge_t_fuel"].to_numpy(),
        "t_amb": trace["t_amb"].to_numpy(),
        "rh": trace["rh"].to_numpy(),
        "precip_mm": trace["precip_mm"].to_numpy(),
        "recon_L": trace["recon_L"].to_numpy(),
        "delivered_water_kg": delivered,
        "drained_kg": drained,
        "drain_out_on": np.full(n, float(p.drain_out)),
    }


def build_fleet(years, tanks_per_year=TANKS_PER_YEAR, seed_base=0, city: str = "varanasi",
                overrides: dict | None = None) -> list[TankRun]:
    """Simulate a randomised fleet. `overrides` replaces TankParams fields (stress tests)."""
    from dataclasses import replace

    wx = (load_weather() if city == "varanasi" else load_weather(f"{min(years)}-01-01", f"{max(years)}-12-31", city)).frame
    runs = []
    for y in years:
        rng = Mulberry32(1000 + int(y) + seed_base)
        frame = wx.loc[y]
        for k in range(tanks_per_year):
            seed = int(y) * 100 + k + seed_base
            p = random_params(rng, seed)
            if overrides:
                p = replace(p, **overrides)
            trace, events, ledger = simulate(frame, p)
            runs.append(TankRun(f"{city[:3]}-{y}-{k:02d}", y, p, trace, events, ledger, observables(trace, events, p)))
    return runs


def _window_sum(x, i, steps):
    return float(np.sum(x[max(0, i - steps):i]))


def feature_rows(run: TankRun, origins=None) -> pd.DataFrame:
    """One row per (forecast origin, horizon). Observables only + forecast weather."""
    o = run.obs
    tr = run.trace
    n = len(tr)
    margin = tr["margin"].to_numpy()
    rho_f = value("physical", "density_e20")
    rho_w = value("physical", "density_water")
    cap = run.params.capacity_m3
    drain_steps = np.nonzero(o["drained_kg"] > 0)[0]
    sep_steps = [e["step"] for e in run.events if e["type"] == "separation_onset"]
    origins = range(STEPS_PER_DAY * 3, n - max(HORIZONS_H) * 2, SAMPLE_EVERY) if origins is None else origins
    rows = []
    for i in origins:
        fuel_kg = o["gauge_fuel_m3"][i] * rho_f
        diss = o["sensor_water_mgkg"][i] * 1e-6 * fuel_kg
        bottom = o["gauge_lower_m3"][i] * rho_w
        c_now = float(tolerance_kg(o["t_fuel"][i], fuel_kg, 20.0))
        prev_drains = drain_steps[drain_steps <= i]
        since_drain = (i - prev_drains[-1]) / 2.0 if len(prev_drains) else 1e4
        base = {
            "tank_id": run.tank_id, "year": run.year, "step": i, "time": tr.index[i],
            "margin_now_true": margin[i],
            "est_margin_now": 1.0 - (diss + bottom) / c_now,
            "sensor_water_mgkg": o["sensor_water_mgkg"][i],
            "d_sensor_72h": o["sensor_water_mgkg"][i] - o["sensor_water_mgkg"][max(0, i - 144)],
            "gauge_water_mm": o["gauge_water_mm"][i],
            "d_water_mm_24h": o["gauge_water_mm"][i] - o["gauge_water_mm"][max(0, i - 48)],
            "d_water_mm_72h": o["gauge_water_mm"][i] - o["gauge_water_mm"][max(0, i - 144)],
            "fuel_m3": o["gauge_fuel_m3"][i],
            "ullage_pct": 100 * (1 - o["gauge_fuel_m3"][i] / cap),
            "d_fuel_24h": o["gauge_fuel_m3"][i] - o["gauge_fuel_m3"][max(0, i - 48)],
            "recon_L": o["recon_L"][i],
            "t_fuel": o["t_fuel"][i],
            "t_amb_swing_24h": float(np.ptp(o["t_amb"][max(0, i - 48):i + 1])),
            "rh_mean_24h": float(np.mean(o["rh"][max(0, i - 48):i + 1])),
            "precip_24h": _window_sum(o["precip_mm"], i + 1, 48),
            "precip_72h": _window_sum(o["precip_mm"], i + 1, 144),
            "hours_since_drain": since_drain,
            "drain_out_on": o["drain_out_on"][i],
        }
        for h in HORIZONS_H:
            j = i + h * 2
            fut = slice(i + 1, j + 1)
            row = dict(base)
            row.update({
                "horizon_h": h,
                "fcst_precip_h": float(np.sum(o["precip_mm"][fut])),
                "fcst_t_fuel_h": o["t_fuel"][j],
                "fcst_t_fuel_min_h": float(np.min(o["t_fuel"][fut])),
                "target_margin": margin[j],
                "separated_now": bool(margin[i] <= 0),
                "onset_within_h": any(i < s <= j for s in sep_steps),
            })
            rows.append(row)
    return pd.DataFrame(rows)


FEATURES = [
    "est_margin_now", "sensor_water_mgkg", "d_sensor_72h", "gauge_water_mm", "d_water_mm_24h",
    "d_water_mm_72h", "fuel_m3", "ullage_pct", "d_fuel_24h", "recon_L", "t_fuel", "t_amb_swing_24h",
    "rh_mean_24h", "precip_24h", "precip_72h", "hours_since_drain", "drain_out_on", "horizon_h",
    "fcst_precip_h", "fcst_t_fuel_h", "fcst_t_fuel_min_h",
]
