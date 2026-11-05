"""Layer A: PLS regression of ethanol and water content from Raman spectra.

Protocol (no test-set tuning):
  * model selection (preprocessing recipe, crop window, number of latent
    variables) by 10-fold cross-validation on train + validation;
  * refit the selected pipeline on train + validation;
  * evaluate ONCE on the held-out test split.

Number of latent variables: smallest A whose RMSECV is within one standard
error of the minimum (one-SE rule, DESIGN CHOICE to avoid over-fitting).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
from scipy import stats
from sklearn.cross_decomposition import PLSRegression
from sklearn.linear_model import LinearRegression, RidgeCV
from sklearn.model_selection import KFold

from common.config import ARTEFACTS, value
from layer_a.load import TARGET_ETHANOL, TARGET_WATER, RamanData, load
from layer_a.preprocess import CROPS, MSC, RECIPES, make_preprocessor

SEED = 0
N_FOLDS = 10
MAX_LV = 20
TARGETS = {
    "ethanol": {"column": TARGET_ETHANOL, "unit": "% v/v"},
    "water": {"column": TARGET_WATER, "unit": "mg/kg (assumed; units not stated on dataset card)"},
}


# ----------------------------------------------------------------- metrics
def metrics(y_ref: np.ndarray, y_pred: np.ndarray, n_lv: int | None = None) -> dict:
    e = y_pred - y_ref
    n = len(e)
    bias = float(e.mean())
    sep = float(np.sqrt(((e - bias) ** 2).sum() / (n - 1)))
    rmsep = float(np.sqrt((e**2).mean()))
    ss_res = float((e**2).sum())
    ss_tot = float(((y_ref - y_ref.mean()) ** 2).sum())
    out = {
        "n": n,
        "r2": 1 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        "rmsep": rmsep,
        "sep": sep,
        "bias": bias,
        "rpd": float(y_ref.std(ddof=1) / sep) if sep > 0 else float("nan"),
    }
    if n_lv is not None:
        out["n_lv"] = n_lv
    return out


# ------------------------------------------------------------ PLS helpers
def vip_scores(pls: PLSRegression) -> np.ndarray:
    t = pls.x_scores_
    w = pls.x_weights_
    q = pls.y_loadings_
    p = w.shape[0]
    ss = (q**2).sum(axis=0) * (t**2).sum(axis=0)
    wn = w / np.linalg.norm(w, axis=0, keepdims=True)
    return np.sqrt(p * (wn**2 @ ss) / ss.sum())


def linear_form(pls: PLSRegression, n_features: int) -> tuple[np.ndarray, float]:
    """Return (beta, b0) such that pls.predict(X) == X @ beta + b0 exactly."""
    b0 = float(pls.predict(np.zeros((1, n_features))).ravel()[0])
    beta = pls.predict(np.eye(n_features)).ravel() - b0
    return beta, b0


@dataclass
class Selection:
    recipe: str
    crop: str
    n_lv: int
    rmsecv: float
    cv_curve: list = field(default_factory=list)       # RMSECV per LV for the chosen recipe
    cv_curve_se: list = field(default_factory=list)
    table: list = field(default_factory=list)          # one row per (recipe, crop)


def _stateless(recipe: str) -> bool:
    return not any(isinstance(f(None), MSC) for _, f in RECIPES[recipe])


def cv_curve(X, y, wn, recipe, crop, folds) -> tuple[np.ndarray, np.ndarray]:
    """RMSECV (and its SE across folds) for 1..MAX_LV latent variables."""
    max_lv = min(MAX_LV, int(len(y) * 0.8) - 2)
    fold_mse = np.zeros((len(folds), max_lv))
    if _stateless(recipe):  # per-spectrum transforms: no information crosses rows
        Xp_all = make_preprocessor(recipe, crop, wn).fit_transform(X)
    for k, (tr, te) in enumerate(folds):
        if _stateless(recipe):
            Xtr, Xte = Xp_all[tr], Xp_all[te]
        else:
            pre = make_preprocessor(recipe, crop, wn).fit(X[tr])
            Xtr, Xte = pre.transform(X[tr]), pre.transform(X[te])
        pls = PLSRegression(n_components=max_lv, scale=False).fit(Xtr, y[tr])
        # predictions for every A from one fit: accumulate per-component contributions
        xc = Xte - pls._x_mean
        t = xc @ pls.x_rotations_
        contrib = t * pls.y_loadings_[0]  # (n_te, A)
        pred = pls._y_mean[0] + np.cumsum(contrib, axis=1)
        fold_mse[k] = ((pred - y[te, None]) ** 2).mean(axis=0)
    rmse = np.sqrt(fold_mse.mean(axis=0))
    se = np.sqrt(fold_mse).std(axis=0, ddof=1) / np.sqrt(len(folds))
    return rmse, se


def select(X, y, wn) -> Selection:
    folds = list(KFold(N_FOLDS, shuffle=True, random_state=SEED).split(X))
    best = None
    table = []
    curves = {}
    for recipe in RECIPES:
        for crop in CROPS:
            rmse, se = cv_curve(X, y, wn, recipe, crop, folds)
            i_min = int(np.argmin(rmse))
            n_lv = int(np.argmax(rmse <= rmse[i_min] + se[i_min])) + 1
            row = {"recipe": recipe, "crop": crop, "n_lv": n_lv, "rmsecv": float(rmse[n_lv - 1]),
                   "rmsecv_min": float(rmse[i_min]), "n_lv_min": i_min + 1}
            table.append(row)
            curves[(recipe, crop)] = (rmse, se)
            if best is None or row["rmsecv"] < best["rmsecv"]:
                best = row
    rmse, se = curves[(best["recipe"], best["crop"])]
    return Selection(best["recipe"], best["crop"], best["n_lv"], best["rmsecv"],
                     rmse.tolist(), se.tolist(), sorted(table, key=lambda r: r["rmsecv"]))


# ------------------------------------------------------------ fit & export
@dataclass
class FittedModel:
    target: str
    selection: Selection
    pre: object
    pls: PLSRegression
    n_train: int
    y_range: tuple[float, float]
    q_limit: float
    h_limit: float
    tt_inv: np.ndarray

    def transform(self, X):
        return self.pre.transform(np.atleast_2d(X))

    def predict(self, X):
        return self.pls.predict(self.transform(X)).ravel()

    def diagnostics(self, X):
        """Leverage h and spectral residual Q for new spectra."""
        Xp = self.transform(X)
        xc = Xp - self.pls._x_mean
        t = xc @ self.pls.x_rotations_
        h = 1.0 / self.n_train + np.einsum("ij,jk,ik->i", t, self.tt_inv, t)
        resid = xc - t @ self.pls.x_loadings_.T
        q = (resid**2).sum(axis=1)
        return t, h, q


def fit_target(data: RamanData, target: str) -> tuple[FittedModel, dict]:
    col = TARGETS[target]["column"]
    y_all = data.targets[col].to_numpy(dtype=float)
    has = ~np.isnan(y_all)
    dev = has & np.isin(data.split, ["train", "validation"])
    test = has & (data.split == "test")
    X, wn = data.X, data.wavenumbers

    sel = select(X[dev], y_all[dev], wn)
    pre = make_preprocessor(sel.recipe, sel.crop, wn).fit(X[dev])
    Xd = pre.transform(X[dev])
    pls = PLSRegression(n_components=sel.n_lv, scale=False).fit(Xd, y_all[dev])

    t_dev = pls.x_scores_
    tt_inv = np.linalg.inv(t_dev.T @ t_dev)
    resid = (Xd - pls._x_mean) - t_dev @ pls.x_loadings_.T
    q_dev = (resid**2).sum(axis=1)
    n = int(dev.sum())
    model = FittedModel(
        target=target, selection=sel, pre=pre, pls=pls, n_train=n,
        y_range=(float(y_all[dev].min()), float(y_all[dev].max())),
        q_limit=float(np.quantile(q_dev, 0.95)),
        h_limit=float(3 * (sel.n_lv + 1) / n),
        tt_inv=tt_inv,
    )

    # ---- held-out test evaluation (evaluated once, after selection) ----
    y_test = y_all[test]
    pred_test = model.predict(X[test])
    m_pls = metrics(y_test, pred_test, sel.n_lv)

    ridge = RidgeCV(alphas=np.logspace(-3, 6, 40)).fit(Xd, y_all[dev])
    pred_ridge = ridge.predict(pre.transform(X[test]))
    m_ridge = metrics(y_test, pred_ridge)
    m_ridge["alpha"] = float(ridge.alpha_)

    m_mean = metrics(y_test, np.full_like(y_test, y_all[dev].mean()))

    result = {
        "target": target,
        "column": col,
        "unit": TARGETS[target]["unit"],
        "data_label": "REAL DATA",
        "n_dev": n,
        "n_test": int(test.sum()),
        "selection": {
            "recipe": sel.recipe, "crop": sel.crop, "n_lv": sel.n_lv, "rmsecv": sel.rmsecv,
            "cv_curve": sel.cv_curve, "cv_curve_se": sel.cv_curve_se, "table": sel.table,
            "rule": "one-SE rule on 10-fold CV RMSE over train+validation",
        },
        "test": {"pls": m_pls, "ridge": m_ridge, "predict_dev_mean": m_mean},
        "calibration_range": model.y_range,
        "test_ids": data.sample_id[test].tolist(),
        "test_ref": y_test.tolist(),
        "test_pred": pred_test.tolist(),
        "test_pred_ridge": pred_ridge.tolist(),
        "dev_ref": y_all[dev].tolist(),
        "dev_fitted": pls.predict(Xd).ravel().tolist(),
    }

    if target == "water":
        # Is the water model just reading ethanol? Fit water ~ ethanol on dev rows.
        eth = data.targets[TARGET_ETHANOL].to_numpy(dtype=float)
        ok_dev = dev & ~np.isnan(eth)
        ok_test = test & ~np.isnan(eth)
        lr = LinearRegression().fit(eth[ok_dev, None], y_all[ok_dev])
        result["test"]["ethanol_proxy_reference"] = metrics(y_all[ok_test], lr.predict(eth[ok_test, None]))
        result["water_ethanol_corr_dev"] = float(np.corrcoef(eth[ok_dev], y_all[ok_dev])[0, 1])

    return model, result


def prediction_interval(model: FittedModel, X) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (pred, half_width, leverage, Q) for spectra X."""
    level = value("conformity", "prediction_interval_level")
    pred = model.predict(X)
    _, h, q = model.diagnostics(X)
    df = model.n_train - model.selection.n_lv - 1
    tq = stats.t.ppf(0.5 + level / 2, df)
    half = tq * model.selection.rmsecv * np.sqrt(1.0 + h)
    return pred, half, h, q


def export_model(model: FittedModel, wn: np.ndarray) -> dict:
    """Everything the browser needs to reproduce predict() and diagnostics()."""
    n_feat = model.pls.x_rotations_.shape[0]
    beta, b0 = linear_form(model.pls, n_feat)
    level = value("conformity", "prediction_interval_level")
    df = model.n_train - model.selection.n_lv - 1
    steps = [step.export() for _, step in model.pre.steps]
    return {
        "target": model.target,
        "unit": TARGETS[model.target]["unit"],
        "wavenumbers_in": wn.tolist(),
        "preprocessing": steps,
        "x_mean": model.pls._x_mean.tolist(),
        "beta": beta.tolist(),
        "b0": b0,
        "x_rotations": model.pls.x_rotations_.T.tolist(),   # (A, p)
        "x_loadings": model.pls.x_loadings_.T.tolist(),     # (A, p)
        "tt_inv": model.tt_inv.tolist(),
        "n_train": model.n_train,
        "n_lv": model.selection.n_lv,
        "rmsecv": model.selection.rmsecv,
        "t_quantile": float(stats.t.ppf(0.5 + level / 2, df)),
        "pi_level": level,
        "q_limit": model.q_limit,
        "h_limit": model.h_limit,
        "calibration_range": list(model.y_range),
        "vip": vip_scores(model.pls).tolist(),
        "wavenumbers_model": wn[model.pre.steps[0][1].start_:model.pre.steps[0][1].stop_].tolist(),
    }


def run() -> dict:
    data = load()
    ARTEFACTS.mkdir(exist_ok=True)
    out = {}
    for target in TARGETS:
        model, result = fit_target(data, target)
        out[target] = (model, result)
        m = result["test"]["pls"]
        print(f"[{target}] {result['selection']['recipe']} | {result['selection']['crop']} | "
              f"LV={m['n_lv']} | RMSECV={result['selection']['rmsecv']:.3f} | test R2={m['r2']:.3f} "
              f"RMSEP={m['rmsep']:.3f} SEP={m['sep']:.3f} bias={m['bias']:.3f} RPD={m['rpd']:.2f} "
              f"| ridge R2={result['test']['ridge']['r2']:.3f}")
        with open(ARTEFACTS / f"layer_a_{target}_results.json", "w") as f:
            json.dump(result, f, indent=1)
    return out


if __name__ == "__main__":
    run()
