"""Layer B end-to-end: fleet simulation, forecasting, alerts, change points, export.

Everything written here is labelled SYNTHETIC (physics-informed).

Outputs
  artefacts/layer_b_metrics.json
  site/public/data/layer_b/metrics.json     model comparison, alerts, change points, Solution 4 effect
  site/public/data/layer_b/twin.json        default 14-day digital-twin replay + precomputed forecasts
  tests/fixtures/sim_reference.json         Python simulator output for the TS equivalence test
"""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pandas as pd

from common.config import ARTEFACTS, ROOT, SITE_DATA, value
from layer_b import changepoint as cp
from layer_b import models
from layer_b import physics_forecast as pf
from layer_b.dataset import (
    FEATURES,
    HORIZONS_H,
    TEST_YEARS,
    TRAIN_YEARS,
    build_fleet,
    feature_rows,
    observables,
)
from sim.tank import STEPS_PER_DAY, TankParams, simulate
from sim.weather import load as load_weather

OUT = SITE_DATA / "layer_b"
FIXTURES = ROOT / "tests" / "fixtures"
TRAIN_SAMPLE_EVERY = 24  # 12 h between training origins (test: 6 h)

TWIN_SPAN = ("2024-06-01", "2024-08-15 23:30")
TWIN_WINDOW = ("2024-06-26", "2024-07-09 23:30")
TWIN_PARAMS = TankParams(seal="major", seal_fault_start_day=0.0, drain_out=False, seed=0)


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def solution4_effect(runs) -> dict:
    """Controlled experiment: same tank, same weather, drain-out on vs off."""
    wx = load_weather().frame
    rows = []
    for r in runs:
        if r.params.seal == "none":
            continue
        frame = wx.loc[r.year]
        res = {}
        for flag in (False, True):
            tr, ev, _ = simulate(frame, replace(r.params, drain_out=flag))
            onsets = [e["step"] for e in ev if e["type"] == "separation_onset"]
            res[flag] = (len(onsets), onsets[0] / STEPS_PER_DAY if onsets else None, float(tr["margin"].min()))
        rows.append({"tank_id": r.tank_id, "seal": r.params.seal,
                     "incidents_off": res[False][0], "incidents_on": res[True][0],
                     "first_day_off": res[False][1], "first_day_on": res[True][1],
                     "min_margin_off": res[False][2], "min_margin_on": res[True][2]})
    df = pd.DataFrame(rows)
    out = {"n_tanks": len(df), "by_seal": {}}
    for seal, g in df.groupby("seal"):
        both = g.dropna(subset=["first_day_off", "first_day_on"])
        out["by_seal"][seal] = {
            "tanks": len(g),
            "tanks_with_separation_off": int((g.incidents_off > 0).sum()),
            "tanks_with_separation_on": int((g.incidents_on > 0).sum()),
            "incidents_off": int(g.incidents_off.sum()),
            "incidents_on": int(g.incidents_on.sum()),
            "median_delay_days_when_both_separate": float((both.first_day_on - both.first_day_off).median()) if len(both) else None,
        }
    out["rows"] = rows
    return out


def breathing_only(runs) -> dict:
    """Sealed tanks with wet tankers removed: can breathing alone separate E20?"""
    wx = load_weather().frame
    sealed = [r for r in runs if r.params.seal == "none"]
    n_sep, max_vap = 0, 0.0
    for r in sealed:
        tr, ev, _ = simulate(wx.loc[r.year], replace(r.params, wet_tanker_probability=0.0))
        n_sep += any(e["type"] == "separation_onset" for e in ev)
        max_vap = max(max_vap, float(tr["ingress_vapour_kg"].resample("D").sum().max()))
    return {"sealed_tanks": len(sealed), "tanks_separated": n_sep, "max_vapour_uptake_kg_per_day": max_vap}


def twin_export(gbm, gbm_q) -> dict:
    wx = load_weather()
    frame = wx.frame.loc[TWIN_SPAN[0]:TWIN_SPAN[1]]
    tr, ev, ledger = simulate(frame, TWIN_PARAMS)
    obs = observables(tr, ev, TWIN_PARAMS)
    pf.prepare(obs)
    i0 = tr.index.get_loc(pd.Timestamp(TWIN_WINDOW[0]))
    i1 = tr.index.get_loc(pd.Timestamp(TWIN_WINDOW[1]))
    run = type("R", (), {})()
    run.obs, run.trace, run.events, run.params = obs, tr, ev, TWIN_PARAMS
    run.tank_id, run.year = "twin", "2024"
    origins = list(range(i0, i1 + 1, 12))
    feats = feature_rows(run, origins)
    feats["gbm"] = gbm.predict(feats[FEATURES])
    feats["gbm_q"] = gbm_q.predict(feats[FEATURES])
    fc = []
    n = pf.HORIZON_H * pf.STEPS_PER_H
    for i in origins:
        fut = slice(i + 1, i + 1 + n)
        phys = pf.forecast(obs, i, obs["t_fuel"][fut], obs["precip_mm"][fut])
        g = feats[feats.step == i].sort_values("horizon_h")
        fc.append({"step": i, "physics": {k: phys[k] for k in ("mid", "lo", "hi", "a", "b", "time_to_separation_h")},
                   "gbm": g["gbm"].tolist(), "gbm_q": g["gbm_q"].tolist()})
    # change points detected on the full span, reported inside the window
    water_pen = json.loads((ARTEFACTS / "layer_b_metrics.json").read_text())["changepoints"]["water"]["chosen_penalty"] \
        if (ARTEFACTS / "layer_b_metrics.json").exists() else 2560
    cps = [h * 2 for h in cp.detect(cp.hourly(obs["gauge_water_mm"]), water_pen)]
    cols = ["fuel_m3", "ullage_m3", "t_fuel", "t_ullage", "t_amb", "rh", "precip_mm", "dissolved_kg", "bottom_kg",
            "lower_water_kg", "lower_phase_m3", "tolerance_kg", "margin", "water_mgkg", "ethanol_pct", "air_in_m3",
            "ingress_vapour_kg", "ingress_liquid_kg", "gauge_fuel_m3", "gauge_water_mm", "recon_L", "sensor_water_mgkg"]
    return {
        "data_label": "SYNTHETIC (physics-informed)",
        "weather_label": wx.label,
        "weather_source": wx.source,
        "params": TWIN_PARAMS.to_dict(),
        "span": [str(frame.index[0]), str(frame.index[-1])],
        "window_steps": [i0, i1],
        "times": [t.strftime("%Y-%m-%dT%H:%M") for t in frame.index],
        "weather": {k: np.round(frame[k].to_numpy(), 3).tolist() for k in ("t_amb", "rh", "precip_mm", "t_soil")},
        "trace": {k: np.round(tr[k].to_numpy(), 6).tolist() for k in cols},
        "events": ev,
        "ledger": ledger,
        "horizons_h": HORIZONS_H,
        "forecasts": fc,
        "changepoints_steps": cps,
    }


def sim_fixture() -> dict:
    frame = load_weather().frame.loc["2024-06-01":"2024-07-15 23:30"]
    cases = []
    for p in (TankParams(seed=3), TankParams(seal="major", drain_out=True, seed=7, rh_offset=10, swing_scale=1.5),
              TankParams(seal="minor", seal_fault_start_day=5, wet_tanker_probability=0.5, seed=11),
              TankParams(seal="major", tolerance_scale=1.15, catchment_scale=0.5, sensor_sigma_scale=2.0,
                         lower_phase_ethanol_fraction=0.3, drain_out=True, seed=5)):
        tr, ev, led = simulate(frame, p)
        cases.append({"params": p.to_dict(), "events": ev, "ledger": led,
                      "trace": {k: tr[k].tolist() for k in ("fuel_m3", "dissolved_kg", "bottom_kg", "lower_water_kg",
                                                           "margin", "gauge_water_mm", "sensor_water_mgkg", "air_in_m3")}})
    return {"times": [t.strftime("%Y-%m-%dT%H:%M") for t in frame.index],
            "weather": {k: frame[k].tolist() for k in ("t_amb", "rh", "precip_mm", "t_soil")}, "cases": cases}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    ARTEFACTS.mkdir(exist_ok=True)

    print("simulating fleets ...")
    train_runs = build_fleet(TRAIN_YEARS)
    test_runs = build_fleet(TEST_YEARS)
    for r in train_runs + test_runs:
        assert abs(r.ledger["imbalance"]) < 1e-6, r.tank_id

    print("building tables ...")
    train = pd.concat([feature_rows(r, range(STEPS_PER_DAY * 3, len(r.trace) - 144, TRAIN_SAMPLE_EVERY))
                       for r in train_runs], ignore_index=True)
    test = models.table(test_runs)
    assert set(train.tank_id).isdisjoint(set(test.tank_id))
    assert train.time.max() < test.time.min()

    print("training GBM ...")
    gbm = models.fit_gbm(train)
    gbm_q = models.fit_gbm(train, value("alerts", "alert_quantile"))

    print("evaluating ...")
    preds = {"legacy_xgboost": models.predict_legacy(test), "gbm": gbm.predict(test[FEATURES]),
             "physics_rollforward": models.predict_physics(test_runs, test)}
    alerts = {"gbm": gbm_q.predict(test[FEATURES])}
    evaluation = models.evaluate(test, preds, test_runs, alerts)

    print("change points ...")
    changepoints = {s: cp.tune_and_test(train_runs, test_runs, s) for s in ("water", "recon")}

    print("solution 4 experiment ...")
    sol4 = solution4_effect(train_runs + test_runs)

    def fleet_summary(runs):
        seals = pd.Series([r.params.seal for r in runs]).value_counts().to_dict()
        return {"tanks": len(runs), "seal_mix": seals,
                "drain_out_on": int(sum(r.params.drain_out for r in runs)),
                "incidents": int(sum(e["type"] == "separation_onset" for r in runs for e in r.events)),
                "max_mass_imbalance_kg": float(max(abs(r.ledger["imbalance"]) for r in runs))}

    imp = dict(zip(FEATURES, gbm.feature_importances_.tolist(), strict=True))
    metrics = {
        "data_label": "SYNTHETIC (physics-informed)",
        "split": {"train_years": TRAIN_YEARS, "test_years": TEST_YEARS,
                  "train_rows": len(train), "test_rows": len(test),
                  "train_origin_every_h": TRAIN_SAMPLE_EVERY / 2, "test_origin_every_h": 6},
        "fleet": {"train": fleet_summary(train_runs), "test": fleet_summary(test_runs)},
        "evaluation": evaluation,
        "gbm_feature_importance": dict(sorted(imp.items(), key=lambda kv: -kv[1])),
        "changepoints": changepoints,
        "solution4": {k: v for k, v in sol4.items() if k != "rows"},
        "breathing_only": breathing_only(train_runs + test_runs),
        "alert_config": {k: value("alerts", k) for k in ("watch_horizon_h", "act_horizon_h", "watch_margin",
                                                          "act_margin", "alert_quantile")},
    }
    metrics = _clean(metrics)
    (ARTEFACTS / "layer_b_metrics.json").write_text(json.dumps(metrics, indent=1))
    (OUT / "metrics.json").write_text(json.dumps(metrics))

    print("twin export ...")
    (OUT / "twin.json").write_text(json.dumps(_clean(twin_export(gbm, gbm_q))))
    (FIXTURES / "sim_reference.json").write_text(json.dumps(_clean(sim_fixture())))

    for name, r in evaluation.items():
        if isinstance(r, dict):
            print(f"{name:20s} MAE={r['margin_mae']:.3f} TTS-MAE={r['tts_mae_h']} "
                  f"recall={r['incident_recall']} lead={r['lead_time_h_median']} prec={r['act_precision']}")
    for s, c in changepoints.items():
        print(s, c["test"])
    print(json.dumps(metrics["solution4"], indent=1))


if __name__ == "__main__":
    main()
