"""Depot conformity check: spectrum -> predicted value +/- PI -> PASS/REVIEW/FAIL.

Decision rule (constants.yaml conformity.method):
  PASS   whole prediction interval inside the limits
  FAIL   whole prediction interval outside the limits
  REVIEW interval straddles a limit, OR the spectrum is outside the
         calibration space (leverage h > h_limit or residual Q > Q_limit),
         OR the prediction is outside the calibration range.
"""

from __future__ import annotations

import numpy as np

from common.config import value
from common.physics import pct_vv_to_mg_per_kg
from layer_a.pls import FittedModel, prediction_interval


def grade_limits() -> dict[str, dict]:
    """Ethanol bands and water limit per declared grade, all from constants.yaml."""
    e20_lo, e20_hi = value("spec", "e20_ethanol_content_range")
    water_mgkg = pct_vv_to_mg_per_kg(value("spec", "e20_max_water_content"))
    return {
        "E10": {"ethanol": [0.0, value("spec", "e10_max_ethanol_content")],
                "source": "en228_2017 Table 1"},
        "E20": {"ethanol": [e20_lo, e20_hi], "source": "is17943_2022 Table 1 (xviii)"},
        "water_max_mg_per_kg": {
            "value": water_mgkg,
            "source": "is17943_2022 Table 1 (xix): 0.050 % v/v, converted with densities from constants.yaml",
        },
    }


def decide(pred: float, half: float, lo: float, hi: float, in_space: bool) -> str:
    a, b = pred - half, pred + half
    if b < lo or a > hi:
        status = "FAIL"
    elif a >= lo and b <= hi:
        status = "PASS"
    else:
        status = "REVIEW"
    if not in_space and status == "PASS":
        status = "REVIEW"
    return status


def check(model: FittedModel, spectrum: np.ndarray, lo: float, hi: float) -> dict:
    pred, half, h, q = prediction_interval(model, np.atleast_2d(spectrum))
    pred, half, h, q = float(pred[0]), float(half[0]), float(h[0]), float(q[0])
    r_lo, r_hi = model.y_range
    in_space = h <= model.h_limit and q <= model.q_limit and r_lo <= pred <= r_hi
    reasons = []
    if h > model.h_limit:
        reasons.append(f"leverage {h:.3f} > {model.h_limit:.3f}")
    if q > model.q_limit:
        reasons.append(f"spectral residual Q {q:.3g} > {model.q_limit:.3g}")
    if not r_lo <= pred <= r_hi:
        reasons.append(f"prediction outside calibration range {r_lo:g}-{r_hi:g}")
    return {
        "target": model.target,
        "prediction": pred,
        "interval": [pred - half, pred + half],
        "limits": [lo, hi],
        "leverage": h,
        "q_residual": q,
        "in_calibration_space": in_space,
        "reasons": reasons,
        "status": decide(pred, half, lo, hi, in_space),
    }
