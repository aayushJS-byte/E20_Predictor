"""Full validation of Layer B (SYNTHETIC tanks, REAL weather).

No public tank-gauge data with water ingress exists, so Layer B is validated by:
  1. external validation on five other Indian cities' real 2024 weather (ERA5):
     models trained on Varanasi 2022-23 only
  2. bootstrap 95 % CIs on alert metrics (resampling whole tanks)
  3. robustness to wrong assumptions: models trained with the configured values, tested on
     fleets where the hidden physics differs (dissolution rate, leak catchment, sensor noise,
     lower-phase composition, and a 15 % higher water tolerance, as suggested by the
     Johansen & Schramm measurements)
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from common.config import ARTEFACTS, SITE_DATA, value
from common.jsonio import dump
from layer_b import models
from layer_b.dataset import FEATURES, STEPS_PER_DAY, TRAIN_YEARS, build_fleet, feature_rows

TANKS = 100
CITIES = ["delhi", "mumbai", "chennai", "kolkata", "guwahati"]
STRESS = {
    "baseline (as configured)": {},
    "settled water dissolves 2x faster": {"dissolution_kg_per_day": "x2"},
    "settled water dissolves 2x slower": {"dissolution_kg_per_day": "x0.5"},
    "leaks 2x larger": {"catchment_scale": 2.0},
    "leaks 2x smaller": {"catchment_scale": 0.5},
    "water test 3x noisier": {"sensor_sigma_scale": 3.0},
    "lower phase 30 % ethanol": {"lower_phase_ethanol_fraction": 0.3},
    "lower phase 70 % ethanol": {"lower_phase_ethanol_fraction": 0.7},
    "tolerance 15 % higher (measured)": {"tolerance_scale": 1.15},
}


def _fleet(city="varanasi", overrides=None, seed_base=7):
    """2024 test fleet. Multiplicative overrides ('x2') scale each tank's own random draw."""
    runs = build_fleet(["2024"], TANKS, seed_base=seed_base, city=city)
    if overrides and any(isinstance(v, str) for v in overrides.values()):
        from dataclasses import replace

        from layer_b.dataset import observables
        from sim.tank import simulate
        from sim.weather import load as load_weather

        wx = load_weather().frame.loc["2024"]
        out = []
        for r in runs:
            kw = {k: getattr(r.params, k) * float(v[1:]) if isinstance(v, str) else v for k, v in overrides.items()}
            p = replace(r.params, **kw)
            tr, ev, led = simulate(wx, p)
            out.append(type(r)(r.tank_id, r.year, p, tr, ev, led, observables(tr, ev, p)))
        return out
    if overrides:
        return build_fleet(["2024"], TANKS, seed_base=seed_base, city=city, overrides=overrides)
    return runs


def _score(runs, gbm, gbm_q) -> dict:
    te = models.table(runs)
    g, q, ph = gbm.predict(te[FEATURES]), gbm_q.predict(te[FEATURES]), models.predict_physics(runs, te)
    # ensemble: ACT only when both models forecast separation (max of the two margins)
    preds = {"gbm": g, "physics_rollforward": ph, "ensemble": 0.5 * (g + ph)}
    ev = models.evaluate(te, preds, runs, {"gbm": q, "ensemble": np.maximum(q, ph)})
    out = {"n_tanks": len(runs), "n_incidents": ev["n_incidents"],
           "rain_mm_mean": float(np.mean([r.trace["precip_mm"].sum() for r in runs]))}
    for k in preds:
        m = ev[k]
        out[k] = {"incident_recall": m["incident_recall"], "act_precision": m["act_precision"],
                  "lead_time_h_median": m["lead_time_h_median"], "margin_mae_72h": m["margin_mae_by_h"][72],
                  "ci95": models.bootstrap_alerts(m["per_tank"])}
    return out


def run() -> dict:
    t0 = time.time()
    print("training on Varanasi 2022-23 ...", flush=True)
    train_runs = build_fleet(TRAIN_YEARS)
    train = pd.concat([feature_rows(r, range(STEPS_PER_DAY * 3, len(r.trace) - 144, 24)) for r in train_runs], ignore_index=True)
    gbm = models.fit_gbm(train)
    gbm_q = models.fit_gbm(train, value("alerts", "alert_quantile"))
    res: dict = {"data_label": "SYNTHETIC tanks, REAL DATA (ERA5) weather", "tanks_per_scenario": TANKS,
                 "trained_on": "Varanasi 2022-2023 weather, configured assumptions", "cities": {}, "stress": {}}
    for city in ["varanasi", *CITIES]:
        print(f"city {city} ...", flush=True)
        res["cities"][city] = _score(_fleet(city), gbm, gbm_q)
        _print(city, res["cities"][city])
    for name, ov in STRESS.items():
        if name.startswith("baseline"):
            res["stress"][name] = res["cities"]["varanasi"]
            continue
        print(f"stress {name} ...", flush=True)
        res["stress"][name] = _score(_fleet("varanasi", ov), gbm, gbm_q)
        _print(name, res["stress"][name])
    res["runtime_s"] = time.time() - t0
    (SITE_DATA / "validation").mkdir(parents=True, exist_ok=True)
    dump(res, ARTEFACTS / "validation_layer_b.json", indent=1)
    dump(res, SITE_DATA / "validation" / "layer_b.json")
    return res


def _print(name, r):
    g, p, e = r["gbm"], r["physics_rollforward"], r["ensemble"]
    f = lambda x, k=2: "-" if x is None else f"{x:.{k}f}"  # noqa: E731
    print(f"  {name:34s} incidents={r['n_incidents']:3d} GBM recall={f(g['incident_recall'])} {g['ci95']['incident_recall']} "
          f"prec={f(g['act_precision'])} lead={f(g['lead_time_h_median'], 0)}h | phys recall={f(p['incident_recall'])} "
          f"prec={f(p['act_precision'])} lead={f(p['lead_time_h_median'], 0)}h | ens recall={f(e['incident_recall'])} "
          f"prec={f(e['act_precision'])} lead={f(e['lead_time_h_median'], 0)}h", flush=True)


if __name__ == "__main__":
    run()
