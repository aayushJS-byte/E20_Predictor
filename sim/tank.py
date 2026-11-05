"""Physics-informed simulator of an E20 underground storage tank (Layer B).

Everything produced here is SYNTHETIC (physics-informed). The weather that
drives it can be real (ERA5), but the tank, its events and its gauges are
simulated. Every parameter comes from config/constants.yaml (many are labelled
ASSUMPTION there).

State, every 30 minutes
  V_fuel   fuel volume (m3), with V_eth ethanol volume inside it
  D        dissolved water (kg)
  B        settled bottom water not yet dissolved (kg)
  S        water in the separated lower (ethanol-water) phase (kg), E_low its ethanol (kg)
  T_fuel   fuel temperature = ground temperature (ERA5 28-100 cm soil)
  T_ull    ullage gas temperature = T_soil + coupling * (T_amb - T_soil)

Processes
  breathing   ullage gas contracts on cooling / when fuel is withdrawn ->
              ambient air drawn in through the open vent; its water vapour is
              absorbed by the fuel (moisture_capture_efficiency). Exhaled gas
              is taken as dry.
  dispensing  daytime withdrawal; dissolved water and ethanol leave pro rata;
              bottom water and lower phase are not dispensed.
  delivery    when fuel drops below the trigger level; delivered fuel is at the
              E20 water limit (IS 17943); a "wet tanker" adds free water to B.
  rain        through a faulty seal: precip x catchment area -> B.
  dissolution B dissolves at a finite rate scaled by (1 - D/C).
  separation  if D + B > C(T_fuel, ethanol %) the tank holds more water than
              the fuel phase can at equilibrium: the settled water (plus any
              dissolved water above C) becomes the lower phase and drags ethanol with it (fixed lower-phase
              composition, ASSUMPTION), which lowers the fuel's ethanol content
              and hence its tolerance.
  drain-out   Solution 4 routine: removes B and the lower phase.

Mass balance (tested): water_in - water_out == (D + B + S)_end - (D + B + S)_start
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from common.config import value
from common.physics import pct_vv_to_mg_per_kg, tolerance_kg

DT_S = 1800.0
STEPS_PER_DAY = 48


# ------------------------------------------------------------------ PRNG
class Mulberry32:
    """Tiny deterministic PRNG, identical in site/src/lib/sim.ts."""

    def __init__(self, seed: int):
        self.a = seed & 0xFFFFFFFF

    def random(self) -> float:
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    def normal(self) -> float:
        u1 = max(self.random(), 1e-12)
        u2 = self.random()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


# ------------------------------------------------------------------ params
@dataclass
class TankParams:
    capacity_m3: float = field(default_factory=lambda: value("tank", "capacity_m3"))
    initial_fill_fraction: float = field(default_factory=lambda: value("tank", "initial_fill_fraction"))
    delivery_trigger_fraction: float = field(default_factory=lambda: value("tank", "delivery_trigger_fraction"))
    delivery_volume_m3: float = field(default_factory=lambda: value("tank", "delivery_volume_m3"))
    dispense_m3_per_day: float = field(default_factory=lambda: value("tank", "dispense_m3_per_day"))
    ullage_ambient_coupling: float = field(default_factory=lambda: value("tank", "ullage_ambient_coupling"))
    moisture_capture_efficiency: float = field(default_factory=lambda: value("tank", "moisture_capture_efficiency"))
    seal: str = "none"                     # none | minor | major
    seal_fault_start_day: float = 0.0      # day index (from run start) at which the seal fails
    wet_tanker_probability: float = field(default_factory=lambda: value("tank", "wet_tanker_probability"))
    wet_tanker_water_L: float = field(default_factory=lambda: value("tank", "wet_tanker_water_L"))
    dissolution_kg_per_day: float = field(default_factory=lambda: value("tank", "bottom_water_dissolution_kg_per_day"))
    drain_out: bool = False
    drain_interval_days: float = field(default_factory=lambda: value("tank", "drain_out_interval_days"))
    drain_fraction: float = field(default_factory=lambda: value("tank", "drain_out_removes_free_phase_fraction"))
    ethanol_pct: float = 20.0
    rh_offset: float = 0.0                 # slider: added to ambient RH (percentage points)
    swing_scale: float = 1.0               # slider: scales ambient deviation from its 24 h mean
    seed: int = 0
    # validation-only stress knobs (1.0 / None = the configured values)
    tolerance_scale: float = 1.0
    catchment_scale: float = 1.0
    sensor_sigma_scale: float = 1.0
    lower_phase_ethanol_fraction: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _constants() -> dict:
    return {
        "R": value("physical", "gas_constant"),
        "Mw": value("physical", "molar_mass_water"),
        "P": value("physical", "atmospheric_pressure"),
        "rho_w": value("physical", "density_water"),
        "rho_f": value("physical", "density_e20"),
        "rho_e": value("physical", "density_ethanol"),
        "magnus": value("physical", "magnus"),
        "f_low": value("lower_phase", "ethanol_mass_fraction"),
        "catch": value("tank", "seal_fault_catchment_m2"),
        "diam": value("tank", "tank_diameter_m"),
        "noise_h_mm": value("tank", "gauge_noise_water_level_mm"),
        "noise_v_L": value("tank", "gauge_noise_fuel_volume_L"),
        "sensor_sigma": value("tank", "water_sensor_sigma_mg_per_kg"),
        "sample_h": value("tank", "water_sample_interval_h"),
        "w_delivered_mgkg": pct_vv_to_mg_per_kg(value("spec", "e20_max_water_content")),
    }


def _psat(t, m):
    return 100.0 * m["A_hPa"] * math.exp(m["B"] * t / (m["C_degC"] + t))


def segment_volume(h: float, radius: float, length: float) -> float:
    if h <= 0:
        return 0.0
    h = min(h, 2 * radius)
    return length * (radius**2 * math.acos((radius - h) / radius) - (radius - h) * math.sqrt(2 * radius * h - h * h))


def segment_height(v: float, radius: float, length: float) -> float:
    if v <= 0:
        return 0.0
    lo, hi = 0.0, 2 * radius
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if segment_volume(mid, radius, length) < v:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def ambient_with_sliders(weather: pd.DataFrame, p: TankParams) -> tuple[np.ndarray, np.ndarray]:
    t = weather["t_amb"].to_numpy()
    # explicit centred 24 h mean over samples [i-24, i+23], truncated at the ends (mirrored in sim.ts)
    half = STEPS_PER_DAY // 2
    cs = np.concatenate([[0.0], np.cumsum(t)])
    idx = np.arange(len(t))
    lo = np.maximum(idx - half, 0)
    hi = np.minimum(idx + half, len(t))
    mean24 = (cs[hi] - cs[lo]) / (hi - lo)
    t_amb = mean24 + p.swing_scale * (t - mean24)
    rh = np.clip(weather["rh"].to_numpy() + p.rh_offset, 0.0, 100.0)
    return t_amb, rh


# ------------------------------------------------------------------ run
def simulate(weather: pd.DataFrame, p: TankParams | None = None) -> tuple[pd.DataFrame, list[dict], dict]:
    """Run the tank over `weather` (30-min rows). Returns (trace, events, ledger)."""
    p = p or TankParams()
    c = _constants()
    if p.lower_phase_ethanol_fraction is not None:
        c["f_low"] = p.lower_phase_ethanol_fraction
    c["sensor_sigma"] *= p.sensor_sigma_scale
    ev_rng = Mulberry32(p.seed * 2 + 1)
    noise_rng = Mulberry32(p.seed * 2 + 2)

    t_amb_arr, rh_arr = ambient_with_sliders(weather, p)
    t_soil_arr = weather["t_soil"].to_numpy()
    precip_arr = weather["precip_mm"].to_numpy()
    times = weather.index
    hours = (times.hour + times.minute / 60.0).to_numpy()
    n = len(weather)

    radius = c["diam"] / 2
    length = p.capacity_m3 / (math.pi * radius**2)
    catchment = c["catch"][p.seal] * p.catchment_scale
    seal_start = int(p.seal_fault_start_day * STEPS_PER_DAY)
    disp_rate = p.dispense_m3_per_day / 16.0 / 2.0  # m3 per 30 min, 06:00-22:00

    V = p.initial_fill_fraction * p.capacity_m3
    V_eth = V * p.ethanol_pct / 100.0
    D = c["w_delivered_mgkg"] * 1e-6 * V * c["rho_f"]
    B = S = E_low = 0.0
    book = V
    ledger = {"in_breathing": 0.0, "in_rain": 0.0, "in_wet_tanker": 0.0, "in_delivery_dissolved": 0.0,
              "out_dispensed": 0.0, "out_drained": 0.0, "stored_start": D + B + S}
    events: list[dict] = []
    last_delivery = -10**9
    last_drain_day = -1
    separated = False
    rho_low = 1.0 / (c["f_low"] / c["rho_e"] + (1 - c["f_low"]) / c["rho_w"])

    cols = {k: np.zeros(n) for k in (
        "fuel_m3", "ullage_m3", "t_fuel", "t_ullage", "t_amb", "rh", "precip_mm",
        "dissolved_kg", "bottom_kg", "lower_water_kg", "lower_phase_m3", "tolerance_kg",
        "margin", "water_mgkg", "ethanol_pct", "air_in_m3", "ingress_vapour_kg", "ingress_liquid_kg",
        "gauge_fuel_m3", "gauge_water_mm", "gauge_t_fuel", "book_m3", "recon_L", "sensor_water_mgkg")}

    T_ull_prev = t_soil_arr[0] + p.ullage_ambient_coupling * (t_amb_arr[0] - t_soil_arr[0])
    U_prev = p.capacity_m3 - V
    next_sample = 0.0

    for i in range(n):
        t_amb, rh, t_soil, precip, hr = t_amb_arr[i], rh_arr[i], t_soil_arr[i], precip_arr[i], hours[i]
        T_fuel = t_soil
        T_ull = t_soil + p.ullage_ambient_coupling * (t_amb - t_soil)
        day = i // STEPS_PER_DAY

        # --- delivery (08:00-18:00, at most one per 6 h)
        if V < p.delivery_trigger_fraction * p.capacity_m3 and 8 <= hr < 18 and i - last_delivery >= 12:
            vol = min(p.delivery_volume_m3, 0.95 * p.capacity_m3 - V)
            w_in = c["w_delivered_mgkg"] * 1e-6 * vol * c["rho_f"]
            V += vol
            V_eth += vol * p.ethanol_pct / 100.0
            D += w_in
            book += vol
            ledger["in_delivery_dissolved"] += w_in
            wet = ev_rng.random() < p.wet_tanker_probability
            ev = {"step": i, "type": "delivery", "volume_m3": vol, "wet": bool(wet)}
            if wet:
                wkg = p.wet_tanker_water_L * c["rho_w"] / 1000.0
                B += wkg
                ledger["in_wet_tanker"] += wkg
                ev["free_water_kg"] = wkg
            events.append(ev)
            last_delivery = i

        # --- dispensing (06:00-22:00)
        withdrawn = 0.0
        if 6 <= hr < 22 and V > 0.05 * p.capacity_m3:
            withdrawn = min(disp_rate, V - 0.05 * p.capacity_m3)
            frac = withdrawn / V
            ledger["out_dispensed"] += D * frac
            D -= D * frac
            V_eth -= V_eth * frac
            V -= withdrawn
            book -= withdrawn

        # --- breathing: gas from last step re-expanded to the new ullage temperature
        U = p.capacity_m3 - V - (S + E_low) / rho_low
        gas_now = U_prev * (T_ull + 273.15) / (T_ull_prev + 273.15)
        air_in = max(0.0, U - gas_now)
        n_in = c["P"] * air_in / (c["R"] * (T_ull + 273.15))
        pv = _psat(t_amb, c["magnus"]) * rh / 100.0
        w_vap = p.moisture_capture_efficiency * n_in * (pv / c["P"]) * c["Mw"]
        D += w_vap
        ledger["in_breathing"] += w_vap

        # --- rain through a faulty seal
        w_rain = 0.0
        if catchment > 0 and i >= seal_start and precip > 0:
            w_rain = precip / 1000.0 * catchment * c["rho_w"]
            B += w_rain
            ledger["in_rain"] += w_rain

        # --- dissolution of bottom water, then equilibrium check
        fuel_mass = V * c["rho_f"]
        eth_pct = 100.0 * V_eth / V
        C = float(tolerance_kg(T_fuel, fuel_mass, eth_pct)) * p.tolerance_scale
        if B > 0 and D < C and S == 0:
            j = min(B, p.dissolution_kg_per_day / STEPS_PER_DAY * (1.0 - D / C))
            B -= j
            D += j
        if D + B > C or (S > 0 and B > 0):
            # More water in the tank than the fuel phase can hold at equilibrium:
            # the settled bottom water becomes the ethanol-water lower phase (it is
            # not dissolved instantly), plus any dissolved water above C (cooling).
            # Once a lower phase exists, newly settled water joins it.
            excess = B + max(0.0, D - C)
            D = min(D, C)
            B = 0.0
            S += excess
            e_drag = excess * c["f_low"] / (1 - c["f_low"])
            e_drag = min(e_drag, 0.9 * V_eth * c["rho_e"])
            E_low += e_drag
            V_eth -= e_drag / c["rho_e"]
            V -= e_drag / c["rho_e"]
            if not separated:
                events.append({"step": i, "type": "separation_onset", "excess_kg": excess})
                separated = True

        # --- drain-out (Solution 4), 07:00 on the scheduled day
        if p.drain_out and day % int(p.drain_interval_days) == 0 and day != last_drain_day and hr == 7.0:
            removed_w = p.drain_fraction * (B + S)
            removed_e = p.drain_fraction * E_low
            ledger["out_drained"] += removed_w
            events.append({"step": i, "type": "drain_out", "water_kg": removed_w, "ethanol_kg": removed_e,
                           "was_separated": S > 0})
            B -= p.drain_fraction * B
            S -= p.drain_fraction * S
            E_low -= removed_e
            if S <= 1e-9:
                S = E_low = 0.0
                separated = False
            last_drain_day = day

        if catchment > 0 and i == seal_start:
            events.append({"step": i, "type": "seal_fault_start", "seal": p.seal})

        # --- gauges (ATG) and periodic dissolved-water test
        low_vol = (S + E_low) / rho_low + B / c["rho_w"]
        h_w = segment_height(low_vol, radius, length) * 1000.0
        gauge_fuel = V + noise_rng.normal() * c["noise_v_L"] / 1000.0
        gauge_h = max(0.0, h_w + noise_rng.normal() * c["noise_h_mm"])
        if i >= next_sample:
            sensor = D / fuel_mass * 1e6 + noise_rng.normal() * c["sensor_sigma"]
            next_sample = i + c["sample_h"] * 2
        else:
            sensor = cols["sensor_water_mgkg"][i - 1] if i > 0 else float("nan")

        C_now = float(tolerance_kg(T_fuel, V * c["rho_f"], 100.0 * V_eth / V)) * p.tolerance_scale
        U = p.capacity_m3 - V - low_vol
        row = {
            "fuel_m3": V, "ullage_m3": U, "t_fuel": T_fuel, "t_ullage": T_ull, "t_amb": t_amb, "rh": rh,
            "precip_mm": precip, "dissolved_kg": D, "bottom_kg": B, "lower_water_kg": S,
            "lower_phase_m3": (S + E_low) / rho_low, "tolerance_kg": C_now,
            # <= 0 exactly while a lower phase exists (it is not re-mixed by dilution)
            "margin": (1.0 - (D + B + S) / C_now) if S == 0 else min(0.0, 1.0 - (D + B + S) / C_now), "water_mgkg": D / (V * c["rho_f"]) * 1e6,
            "ethanol_pct": 100.0 * V_eth / V, "air_in_m3": air_in, "ingress_vapour_kg": w_vap,
            "ingress_liquid_kg": w_rain, "gauge_fuel_m3": gauge_fuel, "gauge_water_mm": gauge_h,
            "gauge_t_fuel": T_fuel, "book_m3": book, "recon_L": (gauge_fuel - book) * 1000.0,
            "sensor_water_mgkg": sensor,
        }
        for k, v in row.items():
            cols[k][i] = v
        U_prev, T_ull_prev = U, T_ull

    ledger["stored_end"] = D + B + S
    ledger["water_in"] = sum(ledger[k] for k in ledger if k.startswith("in_"))
    ledger["water_out"] = ledger["out_dispensed"] + ledger["out_drained"]
    ledger["imbalance"] = ledger["water_in"] - ledger["water_out"] - (ledger["stored_end"] - ledger["stored_start"])
    trace = pd.DataFrame(cols, index=times)
    return trace, events, ledger
