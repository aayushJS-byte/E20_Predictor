"""Full validation of Layer A (REAL DATA, Raman).

Beyond the single held-out test split:
  1. bootstrap 95 % CIs of the test metrics
  2. repeated nested cross-validation on all labelled samples
     (outer 5-fold x 10 repeats; the whole selection procedure runs inside each outer fold)
  3. y-randomisation (permutation) test: is the test error better than chance?
  4. prediction-interval coverage (test set and nested CV)
  5. model comparison (PLS, ridge, SVR, random forest, gradient boosting) on the same split
  6. learning curve (test error vs number of calibration samples)
  7. error by fuel grade (E0 / E5 / E10)
  8. every reference property in the dataset (12 targets), not just ethanol and water
"""

from __future__ import annotations

import json
import time

import numpy as np
from scipy import stats
from sklearn.cross_decomposition import PLSRegression
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GridSearchCV, KFold, RepeatedKFold
from sklearn.svm import SVR

from common.config import ARTEFACTS, SITE_DATA, value
from common.jsonio import dump
from layer_a.load import TARGET_ETHANOL, TARGET_WATER, load
from layer_a.pls import metrics, select
from layer_a.preprocess import make_preprocessor

SEED = 0
N_BOOT = 5000
N_PERM = 200


def _fit_predict(Xd, yd, Xt, wn, sel=None):
    """Run the Layer A procedure on (Xd, yd) and predict Xt. Returns (pred, half, sel)."""
    sel = sel or select(Xd, yd, wn)
    pre = make_preprocessor(sel.recipe, sel.crop, wn).fit(Xd)
    Pd, Pt = pre.transform(Xd), pre.transform(Xt)
    pls = PLSRegression(n_components=sel.n_lv, scale=False).fit(Pd, yd)
    t = pls.x_scores_
    tt_inv = np.linalg.inv(t.T @ t)
    tn = (Pt - pls._x_mean) @ pls.x_rotations_
    h = 1 / len(yd) + np.einsum("ij,jk,ik->i", tn, tt_inv, tn)
    q = stats.t.ppf(0.5 + value("conformity", "prediction_interval_level") / 2, len(yd) - sel.n_lv - 1)
    return pls.predict(Pt).ravel(), q * sel.rmsecv * np.sqrt(1 + h), sel


def bootstrap_ci(ref, pred, n=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ref), (n, len(ref)))
    out = {}
    for k in ("r2", "rmsep", "sep", "bias", "rpd"):
        vals = np.array([metrics(ref[i], pred[i])[k] for i in idx])
        out[k] = [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]
    return out


def nested_cv(X, y, wn, repeats=10, folds=5):
    sels, per_fold = [], []
    rkf = RepeatedKFold(n_splits=folds, n_repeats=repeats, random_state=SEED)
    oof = np.full((repeats, len(y)), np.nan)
    oof_half = np.full((repeats, len(y)), np.nan)
    for k, (tr, te) in enumerate(rkf.split(X)):
        p, hw, sel = _fit_predict(X[tr], y[tr], X[te], wn)
        oof[k // folds, te] = p
        oof_half[k // folds, te] = hw
        sels.append(f"{sel.recipe} | {sel.crop} | {sel.n_lv} LV")
        per_fold.append(metrics(y[te], p)["rmsep"])
    rmseps = [metrics(y, oof[r])["rmsep"] for r in range(repeats)]
    r2s = [metrics(y, oof[r])["r2"] for r in range(repeats)]
    cover = float(np.mean(np.abs(oof - y) <= oof_half))
    from collections import Counter

    return {"repeats": repeats, "folds": folds, "rmsep_mean": float(np.mean(rmseps)), "rmsep_sd": float(np.std(rmseps, ddof=1)),
            "rmsep_range": [float(min(rmseps)), float(max(rmseps))], "r2_mean": float(np.mean(r2s)),
            "pi_coverage": cover, "selected_pipelines": Counter(sels).most_common(5),
            "oof_mean_pred": np.nanmean(oof, axis=0).tolist()}


def permutation_test(Xd, yd, Xt, yt, wn, sel, n=N_PERM, seed=SEED):
    """y-randomisation with the selected pipeline held fixed (LV count re-chosen per permutation)."""
    rng = np.random.default_rng(seed)
    real = metrics(yt, _fit_predict(Xd, yd, Xt, wn, sel)[0])["rmsep"]
    pre = make_preprocessor(sel.recipe, sel.crop, wn).fit(Xd)
    Pd, Pt = pre.transform(Xd), pre.transform(Xt)
    folds = list(KFold(10, shuffle=True, random_state=SEED).split(Pd))
    null = []
    for _ in range(n):
        yp = rng.permutation(yd)
        best = None
        for a in range(1, 16):
            e = np.mean([np.mean((PLSRegression(a, scale=False).fit(Pd[tr], yp[tr]).predict(Pd[te]).ravel() - yp[te]) ** 2) for tr, te in folds])
            best = (e, a) if best is None or e < best[0] else best
        null.append(metrics(yt, PLSRegression(best[1], scale=False).fit(Pd, yp).predict(Pt).ravel())["rmsep"])
    null = np.array(null)
    return {"n_permutations": n, "real_rmsep": real, "null_rmsep_median": float(np.median(null)),
            "null_rmsep_p05": float(np.percentile(null, 5)), "p_value": float((np.sum(null <= real) + 1) / (n + 1))}


def model_zoo(Xd, yd, Xt, yt, wn, sel):
    pre = make_preprocessor(sel.recipe, sel.crop, wn).fit(Xd)
    Pd, Pt = pre.transform(Xd), pre.transform(Xt)
    cv = KFold(5, shuffle=True, random_state=SEED)
    models = {
        "PLS (selected)": None,
        "Ridge": RidgeCV(alphas=np.logspace(-3, 6, 40)),
        "SVR (RBF)": GridSearchCV(SVR(), {"C": [1, 10, 100, 1000], "gamma": ["scale", 1e-3, 1e-4], "epsilon": [0.05, 0.2]}, cv=cv),
        "Random forest": RandomForestRegressor(500, min_samples_leaf=2, random_state=SEED, n_jobs=-1),
        "Gradient boosting": GridSearchCV(HistGradientBoostingRegressor(random_state=SEED),
                                          {"learning_rate": [0.03, 0.1], "max_depth": [2, 4], "max_iter": [200, 500]}, cv=cv),
    }
    out = {}
    for name, m in models.items():
        if m is None:
            p = _fit_predict(Xd, yd, Xt, wn, sel)[0]
        else:
            p = m.fit(Pd, yd).predict(Pt)
        out[name] = metrics(yt, p)
    return out


def learning_curve(Xd, yd, Xt, yt, wn, sel, sizes=(20, 30, 45, 60, 80, 100), reps=10):
    rng = np.random.default_rng(SEED)
    res = []
    for n in sizes:
        if n >= len(yd):
            continue
        r = []
        for _ in range(reps):
            i = rng.choice(len(yd), n, replace=False)
            try:
                s2 = select(Xd[i], yd[i], wn)
                r.append(metrics(yt, _fit_predict(Xd[i], yd[i], Xt, wn, s2)[0])["rmsep"])
            except Exception:  # noqa: BLE001 - tiny subsets can fail CV
                continue
        res.append({"n": n, "rmsep_mean": float(np.mean(r)), "rmsep_sd": float(np.std(r))})
    res.append({"n": len(yd), "rmsep_mean": metrics(yt, _fit_predict(Xd, yd, Xt, wn, sel)[0])["rmsep"], "rmsep_sd": 0.0})
    return res


def by_grade(ref, pred):
    bins = {"E0 (< 1 %)": (-1, 1), "E5 (3-6 %)": (3, 6.5), "E10 (6.5-10.5 %)": (6.5, 10.5)}
    out = {}
    for k, (lo, hi) in bins.items():
        m = (ref >= lo) & (ref < hi)
        if m.sum() >= 3:
            e = pred[m] - ref[m]
            out[k] = {"n": int(m.sum()), "rmsep": float(np.sqrt(np.mean(e**2))), "bias": float(e.mean())}
    return out


def run() -> dict:
    t0 = time.time()
    d = load()
    wn = d.wavenumbers
    res: dict = {"data_label": "REAL DATA", "targets": {}}
    for col in d.targets.columns:
        y = d.targets[col].to_numpy(float)
        has = ~np.isnan(y)
        dev = has & np.isin(d.split, ["train", "validation"])
        tst = has & (d.split == "test")
        if tst.sum() < 5 or dev.sum() < 15:
            res["targets"][col] = {"skipped": f"too few labelled samples (dev {int(dev.sum())}, test {int(tst.sum())})"}
            continue
        Xd, yd, Xt, yt = d.X[dev], y[dev], d.X[tst], y[tst]
        p, hw, sel = _fit_predict(Xd, yd, Xt, wn)
        m = metrics(yt, p, sel.n_lv)
        entry = {"n_dev": int(dev.sum()), "n_test": int(tst.sum()), "pipeline": f"{sel.recipe} | {sel.crop}", "test": m,
                 "bootstrap_ci95": bootstrap_ci(yt, p), "pi_coverage_test": float(np.mean(np.abs(p - yt) <= hw)),
                 "range": [float(np.nanmin(y)), float(np.nanmax(y))]}
        if col in (TARGET_ETHANOL, TARGET_WATER):
            print(f"[{col}] nested CV ...", flush=True)
            entry["nested_cv"] = nested_cv(d.X[has], y[has], wn)
            print(f"[{col}] permutation test ...", flush=True)
            entry["permutation"] = permutation_test(Xd, yd, Xt, yt, wn, sel)
            print(f"[{col}] model zoo ...", flush=True)
            entry["models"] = model_zoo(Xd, yd, Xt, yt, wn, sel)
        if col == TARGET_ETHANOL:
            print("[ethanol] learning curve ...", flush=True)
            entry["learning_curve"] = learning_curve(Xd, yd, Xt, yt, wn, sel)
            entry["by_grade_test"] = by_grade(yt, p)
            entry["by_grade_nested"] = by_grade(y[has], np.array(entry["nested_cv"]["oof_mean_pred"]))
        if "nested_cv" in entry:
            entry["nested_cv"].pop("oof_mean_pred", None)
        res["targets"][col] = entry
        print(f"  {col:32s} R2={m['r2']:.3f} RMSEP={m['rmsep']:.3g} RPD={m['rpd']:.2f} CI(R2)={np.round(entry['bootstrap_ci95']['r2'], 2)} "
              f"PIcov={entry['pi_coverage_test']:.2f}", flush=True)
    res["runtime_s"] = time.time() - t0
    (SITE_DATA / "validation").mkdir(parents=True, exist_ok=True)
    dump(res, ARTEFACTS / "validation_layer_a.json", indent=1)
    dump(res, SITE_DATA / "validation" / "layer_a.json")
    return res


if __name__ == "__main__":
    r = run()
    for k in (TARGET_ETHANOL, TARGET_WATER):
        e = r["targets"][k]
        print(k, json.dumps({x: e[x] for x in ("nested_cv", "permutation", "models") if x in e}, indent=1, default=str)[:3000])
