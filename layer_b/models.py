"""Layer B forecasting models and their evaluation (all SYNTHETIC).

(a) legacy  - the original repo's XGBoost (legacy/models/xgb_model.json),
              predicting daily ingress ppm from swing / humidity / vapour space /
              current ppm; projected linearly and converted to a margin.
(b) gbm     - gradient-boosted trees on lagged observables + forecast weather,
              direct multi-horizon (horizon is a feature).
(c) physics - mass-balance roll-forward from observables (physics_forecast.py).

Split: train fleet on 2022-2023 weather, test fleet on 2024 weather.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xgboost as xgb

from common.config import ROOT, value
from common.physics import tolerance_kg
from layer_b import physics_forecast as pf
from layer_b.dataset import FEATURES, HORIZONS_H, TankRun, feature_rows

LEGACY_MODEL = ROOT / "legacy" / "models" / "xgb_model.json"
GBM_PARAMS = dict(n_estimators=500, max_depth=6, learning_rate=0.05, subsample=0.8,
                  colsample_bytree=0.8, random_state=0, n_jobs=4)


def table(runs: list[TankRun]) -> pd.DataFrame:
    return pd.concat([feature_rows(r) for r in runs], ignore_index=True)


def fit_gbm(train: pd.DataFrame, quantile: float | None = None) -> xgb.XGBRegressor:
    """Point model (squared error) or a lower-quantile model used for alerting."""
    params = dict(GBM_PARAMS)
    if quantile is not None:
        params.update(objective="reg:quantileerror", quantile_alpha=quantile)
    m = xgb.XGBRegressor(**params)
    m.fit(train[FEATURES], train["target_margin"])
    return m


def predict_legacy(df: pd.DataFrame) -> np.ndarray:
    model = xgb.XGBRegressor()
    model.load_model(LEGACY_MODEL)
    X = pd.DataFrame({
        "temp_swing_c": df["t_amb_swing_24h"], "humidity_pct": df["rh_mean_24h"],
        "vapor_space_vol": df["ullage_pct"], "current_water_ppm": df["sensor_water_mgkg"],
    })
    rate_ppm_day = model.predict(X)
    ppm = df["sensor_water_mgkg"].to_numpy() + rate_ppm_day * df["horizon_h"].to_numpy() / 24.0
    fuel_kg = df["fuel_m3"].to_numpy() * value("physical", "density_e20")
    c = tolerance_kg(df["fcst_t_fuel_h"].to_numpy(), fuel_kg, 20.0)
    return 1.0 - ppm * 1e-6 * fuel_kg / c


def predict_physics(runs: list[TankRun], df: pd.DataFrame) -> np.ndarray:
    by_id = {r.tank_id: r for r in runs}
    out = np.zeros(len(df))
    cache = {}
    for idx, (tid, step, h) in enumerate(zip(df["tank_id"], df["step"], df["horizon_h"], strict=True)):
        key = (tid, step)
        if key not in cache:
            r = by_id[tid]
            n = pf.HORIZON_H * pf.STEPS_PER_H
            fut = slice(step + 1, step + 1 + n)
            cache[key] = pf.forecast(r.obs, step, r.obs["t_fuel"][fut], r.obs["precip_mm"][fut])["mid"]
        out[idx] = cache[key][h - 1]
    return out


# ---------------------------------------------------------------- metrics
def _tts(margins: np.ndarray) -> float | None:
    return pf.time_to_zero(list(margins), HORIZONS_H)


def evaluate(df: pd.DataFrame, preds: dict[str, np.ndarray], runs: list[TankRun],
             alert_preds: dict[str, np.ndarray] | None = None) -> dict:
    """MAE on point forecasts; alert states from `alert_preds[name]` when given."""
    alert_preds = alert_preds or {}
    act_h = value("alerts", "act_horizon_h")
    watch_h = value("alerts", "watch_horizon_h")
    act_m = value("alerts", "act_margin")
    watch_m = value("alerts", "watch_margin")
    live = ~df["separated_now"].to_numpy()
    out: dict = {"n_origins": int(df.loc[live, ["tank_id", "step"]].drop_duplicates().shape[0])}

    onsets = {(r.tank_id, e["step"]) for r in runs for e in r.events if e["type"] == "separation_onset"}
    out["n_incidents"] = len(onsets)

    for name, p in preds.items():
        d = df.assign(pred=p, apred=alert_preds.get(name, p))[live]
        res = {"margin_mae_by_h": {int(h): float(np.mean(np.abs(g["pred"] - g["target_margin"])))
                                   for h, g in d.groupby("horizon_h")}}
        res["margin_mae"] = float(np.mean(np.abs(d["pred"] - d["target_margin"])))

        # per origin: predicted margin path over the horizon grid -> TTS and alert state
        states, tts_err = [], []
        for (tid, step), g in d.groupby(["tank_id", "step"], sort=False):
            g = g.sort_values("horizon_h")
            pm = g["pred"].to_numpy()
            am = g["apred"].to_numpy()
            hh = g["horizon_h"].to_numpy()
            if np.any(am[hh <= act_h] <= act_m):
                s = "ACT"
            elif np.any(am[hh <= watch_h] < watch_m):
                s = "WATCH"
            else:
                s = "SAFE"
            truth_tts = _tts(g["target_margin"].to_numpy())
            if truth_tts is not None:
                pred_tts = _tts(pm)
                tts_err.append(abs((pred_tts if pred_tts is not None else 72.0) - truth_tts))
            states.append((tid, int(step), s, bool(g["onset_within_h"].to_numpy()[hh <= act_h].any())))
        st = pd.DataFrame(states, columns=["tank_id", "step", "state", "onset_48h"])
        act = st[st.state == "ACT"]
        res["tts_mae_h"] = float(np.mean(tts_err)) if tts_err else None
        res["tts_n"] = len(tts_err)
        res["act_precision"] = float(act["onset_48h"].mean()) if len(act) else None
        res["act_recall_origins"] = float((st.loc[st.onset_48h, "state"] == "ACT").mean()) if st.onset_48h.any() else None
        res["state_counts"] = st["state"].value_counts().to_dict()

        # incident-level lead time: first ACT within the 72 h before onset
        leads, caught = [], 0
        per_tank: dict = {}
        for tid in st.tank_id.unique():
            a = act[act.tank_id == tid]
            per_tank[tid] = {"incidents": 0, "caught": 0, "leads": [], "act": int(len(a)), "act_true": int(a.onset_48h.sum())}
        for tid, s_on in onsets:
            pt = per_tank.setdefault(tid, {"incidents": 0, "caught": 0, "leads": [], "act": 0, "act_true": 0})
            pt["incidents"] += 1
            w = st[(st.tank_id == tid) & (st.step < s_on) & (st.step >= s_on - 144)]
            first = w[w.state == "ACT"]
            if len(first):
                caught += 1
                pt["caught"] += 1
                lead = (s_on - first.step.min()) / 2.0
                leads.append(lead)
                pt["leads"].append(lead)
        res["incident_recall"] = caught / len(onsets) if onsets else None
        res["lead_time_h_median"] = float(np.median(leads)) if leads else None
        res["lead_time_h_all"] = leads
        res["per_tank"] = per_tank
        out[name] = res
    return out


def bootstrap_alerts(per_tank: dict, n: int = 2000, seed: int = 0) -> dict:
    """95 % CIs for incident recall, ACT precision and median lead, resampling whole tanks."""
    rng = np.random.default_rng(seed)
    tanks = list(per_tank.values())
    rec, prec, lead = [], [], []
    for _ in range(n):
        smp = [tanks[i] for i in rng.integers(0, len(tanks), len(tanks))]
        inc = sum(t["incidents"] for t in smp)
        act = sum(t["act"] for t in smp)
        leads = [x for t in smp for x in t["leads"]]
        if inc:
            rec.append(sum(t["caught"] for t in smp) / inc)
        if act:
            prec.append(sum(t["act_true"] for t in smp) / act)
        if leads:
            lead.append(float(np.median(leads)))
    ci = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else None  # noqa: E731
    return {"incident_recall": ci(rec), "act_precision": ci(prec), "lead_time_h_median": ci(lead), "n_boot": n}
