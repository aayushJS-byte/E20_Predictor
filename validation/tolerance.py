"""Validate the water-tolerance correlation against measured phase-separation data.

Data: validation/tolerance_data.py (33 measurements from three independent sources).

Outputs
  * error of the patent correlation (US 8,268,629) per source and for the E5-E30 range
  * an empirically recalibrated tolerance model fitted to the measurements,
    validated by leave-one-out and leave-one-source-out CV
  * artefacts/validation_tolerance.json and site/public/data/validation/tolerance.json
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common.config import ARTEFACTS, SITE_DATA
from common.jsonio import dump
from common.physics import water_tolerance_wt_pct
from validation.tolerance_data import all_measurements


def _design(e: np.ndarray, t: np.ndarray) -> np.ndarray:
    le = np.log(e)
    return np.column_stack([np.ones_like(le), le, le**2, t, t * le])


def fit_recalibrated(df: pd.DataFrame) -> np.ndarray:
    """log(W) = b0 + b1 ln E + b2 ln^2 E + b3 T + b4 T ln E  (least squares)."""
    X = _design(df.ethanol_vol_pct.to_numpy(), df.temp_c.to_numpy())
    beta, *_ = np.linalg.lstsq(X, np.log(df.water_wt_pct.to_numpy()), rcond=None)
    return beta


def predict_recalibrated(beta: np.ndarray, e, t) -> np.ndarray:
    return np.exp(_design(np.atleast_1d(np.asarray(e, float)), np.atleast_1d(np.asarray(t, float))) @ beta)


def _err(obs: np.ndarray, pred: np.ndarray) -> dict:
    e = pred - obs
    return {"n": int(len(obs)), "bias_wt_pct": float(e.mean()), "mae_wt_pct": float(np.abs(e).mean()),
            "mape_pct": float(np.mean(np.abs(e) / obs) * 100), "median_ratio_pred_over_obs": float(np.median(pred / obs))}


def run() -> dict:
    df = all_measurements()
    df["corr_pred"] = water_tolerance_wt_pct(df.temp_c.to_numpy(), df.ethanol_vol_pct.to_numpy())
    out: dict = {"data_label": "LITERATURE VALUE (measured)", "n": len(df)}

    groups = {"all": df, **{s: g for s, g in df.groupby("source")},
              "E5-E30 (fuel-relevant)": df[(df.ethanol_vol_pct >= 4) & (df.ethanol_vol_pct <= 31)],
              "E20 +/- 5": df[(df.ethanol_vol_pct >= 15) & (df.ethanol_vol_pct <= 25)]}
    out["correlation"] = {k: _err(g.water_wt_pct.to_numpy(), g.corr_pred.to_numpy()) for k, g in groups.items()}

    # recalibrated model: fit on fuel-relevant range (E <= 50) to avoid extrapolating the form
    fit_df = df[df.ethanol_vol_pct <= 50].reset_index(drop=True)
    beta = fit_recalibrated(fit_df)
    loo = np.array([predict_recalibrated(fit_recalibrated(fit_df.drop(index=i)), fit_df.ethanol_vol_pct[i], fit_df.temp_c[i])[0]
                    for i in range(len(fit_df))])
    loso = {}
    for s in fit_df.source.unique():
        if s == "haq1990":
            continue
        tr, te = fit_df[fit_df.source != s], fit_df[fit_df.source == s]
        b = fit_recalibrated(tr)
        loso[s] = _err(te.water_wt_pct.to_numpy(), predict_recalibrated(b, te.ethanol_vol_pct, te.temp_c))
    out["recalibrated"] = {
        "form": "ln W = b0 + b1 lnE + b2 ln^2E + b3 T + b4 T lnE   (W wt %, E % v/v, T C)",
        "beta": beta.tolist(), "fit_range": "E <= 50 % v/v, -35 to 21 C",
        "loo": _err(fit_df.water_wt_pct.to_numpy(), loo),
        "leave_one_source_out": loso,
        "in_sample_correlation_same_points": _err(fit_df.water_wt_pct.to_numpy(), fit_df.corr_pred.to_numpy()),
        "e20_at_minus2C": float(predict_recalibrated(beta, 20, -2)[0]),
        "e20_at_25C": float(predict_recalibrated(beta, 20, 25)[0]),
        "note": "Extrapolation above 21 C relies on the fitted temperature slope; the measurements stop at 21 C.",
    }
    out["e20_examples"] = {
        "correlation_minus2C": float(water_tolerance_wt_pct(-2, 20)), "measured_minus2C": 1.64,
        "correlation_minus25C": float(water_tolerance_wt_pct(-25, 20)), "measured_minus25C": 1.32,
    }
    temps = np.arange(-35, 46, 1.0)
    out["curves"] = {
        "temps": temps.tolist(),
        **{f"corr_E{e}": water_tolerance_wt_pct(temps, e).tolist() for e in (10, 20, 25)},
        **{f"recal_E{e}": predict_recalibrated(beta, np.full_like(temps, e), temps).tolist() for e in (10, 20, 25)},
    }
    out["points"] = df[["source", "temp_c", "ethanol_vol_pct", "water_wt_pct", "corr_pred", "ref"]].round(4).to_dict("records")

    (ARTEFACTS).mkdir(exist_ok=True)
    (SITE_DATA / "validation").mkdir(parents=True, exist_ok=True)
    dump(out, ARTEFACTS / "validation_tolerance.json", indent=1)
    dump(out, SITE_DATA / "validation" / "tolerance.json")
    return out


if __name__ == "__main__":
    o = run()
    for k, v in o["correlation"].items():
        print(f"correlation vs {k:24s} n={v['n']:2d} bias={v['bias_wt_pct']:+.3f} MAE={v['mae_wt_pct']:.3f} MAPE={v['mape_pct']:.0f}% pred/obs={v['median_ratio_pred_over_obs']:.2f}")
    r = o["recalibrated"]
    print("recalibrated LOO:", {k: round(x, 3) for k, x in r["loo"].items()})
    print("recalibrated LOSO:", {s: {k: round(x, 3) for k, x in v.items()} for s, v in r["leave_one_source_out"].items()})
    print("correlation on same points:", {k: round(x, 3) for k, x in r["in_sample_correlation_same_points"].items()})
    print("E20:", o["e20_examples"], "recal E20 -2C", round(r["e20_at_minus2C"], 3), "recal E20 25C", round(r["e20_at_25C"], 3))
