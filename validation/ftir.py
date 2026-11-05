"""FTIR-ATR ethanol model on 0-90 % ethanol blends (REAL DATA, lab-prepared blends).

Dataset: Daly, Chen, Comesana, Hagen, Niemeyer & Rapp, "Liquid FTIR-ATR absorption spectra of
aviation and automotive fuels, neat hydrocarbons and alcohols, and their blends", Zenodo
record 21245871 (CC-BY-4.0). Compositions (vol %) are the gravimetric/volumetric recipes in the
record's complete-description.pdf, Tables 3-8.

Why: the Raman dataset stops at 10 % ethanol. These spectra cover E5-E90, including E20, in
gasoline surrogates (n-heptane, isooctane, toluene, and mixtures with methylcyclohexane, 1-hexene,
xylenes, 2-methylbutane), and the mid-IR range includes the O-H stretch.

Validation designs (all on the OSU instrument grid, 650-4000 cm-1):
  * leave-one-family-out: train on every other blend family, test on the held-out family
  * leave-E20-out: drop every 20 % ethanol sample from training, then predict all of them
  * grouped 10-fold CV with E20-band (15-25 %) error
Not covered: commercial gasoline, real E20 from India, water (no water-containing samples).
"""

from __future__ import annotations

import re
import urllib.request
import zipfile

import numpy as np
import pandas as pd
from sklearn.cross_decomposition import PLSRegression
from sklearn.model_selection import GroupKFold

from common.config import ARTEFACTS, ROOT, SITE_DATA
from common.jsonio import dump
from layer_a.pls import metrics
from layer_a.preprocess import SNV, SavGol

DIR = ROOT / "data" / "external" / "ftir_osu"
ZIP_URL = "https://zenodo.org/records/21245871/files/FTIR-ATR-spectra-OSU-LBNL.zip?download=1"
GRID = np.arange(650.0, 4000.0, 2.0)
OTHER_ALCOHOLS = {"methanol", "IPA", "2butanol-REP1", "2butanol-REP2"}
# Truedsson T-series ethanol vol % (complete-description.pdf, Table 5)
T_SERIES = {1: 5, 2: 20, 3: 20, 4: 20, 5: 5, 6: 12.5, 7: 12.5, 8: 5, 9: 12.5, 10: 5, 11: 12.5, 12: 20, 13: 5,
            14: 12.5, 15: 12.5, 16: 20, 17: 12.5}


def download() -> None:
    if any(DIR.rglob("*.CSV")):
        return
    DIR.mkdir(parents=True, exist_ok=True)
    z = DIR / "ftir.zip"
    import subprocess

    try:
        urllib.request.urlretrieve(ZIP_URL, z)
    except Exception:  # noqa: BLE001 - TLS proxies: fall back to curl
        subprocess.run(["curl", "-sL", "--max-time", "600", "-o", str(z), ZIP_URL], check=True)
    zipfile.ZipFile(z).extractall(DIR)


def composition(name: str) -> tuple[float, str] | None:
    """(ethanol vol %, family) from the sample ID, following the description tables."""
    if name in OTHER_ALCOHOLS:
        return None
    if name.startswith("ethanol"):
        return 100.0, "neat ethanol"
    if m := re.fullmatch(r"PRF(\d+)-E(\d+)", name):
        return float(m.group(2)), "PRF + ethanol (Foong)"
    if m := re.fullmatch(r"TERF91-\d+-(\d+)", name):
        return float(m.group(1)), "TRF + ethanol (Foong)"
    if m := re.fullmatch(r"TE(\d+)", name):
        return float(m.group(1)), "toluene + ethanol (Foong)"
    if m := re.fullmatch(r"H\d+E(\d+)", name):
        return float(m.group(1)), "heptane/isooctane + ethanol (Truedsson)"
    if m := re.fullmatch(r"T(\d+)", name):
        return float(T_SERIES[int(m.group(1))]), "4-component + ethanol (Truedsson)"
    return 0.0, "ethanol-free hydrocarbons"


def load() -> pd.DataFrame:
    download()
    rows = []
    for f in sorted(DIR.rglob("*.CSV")):
        if f.name.startswith("._"):
            continue
        a = np.loadtxt(f, delimiter=",")
        if a.shape[0] != 13898:  # second instrument (aviation fuels): different grid
            continue
        comp = composition(f.stem)
        if comp is None:
            continue
        rows.append({"id": f.stem, "ethanol": comp[0], "family": comp[1], "spectrum": np.interp(GRID, a[:, 0], a[:, 1])})
    return pd.DataFrame(rows)


def preprocess(X: np.ndarray, kind: str) -> np.ndarray:
    if kind == "raw":
        return X
    if kind == "snv":
        return SNV().fit_transform(X)
    if kind == "sg1":
        return SavGol(11, 2, 1).fit(X).transform(X)
    raise ValueError(kind)


def choose(X, y, groups, kinds=("raw", "snv", "sg1"), max_lv=15):
    """Pick preprocessing + LVs by grouped 5-fold CV (one-SE rule)."""
    best = None
    gkf = GroupKFold(5)
    for kind in kinds:
        P = preprocess(X, kind)
        errs = np.zeros((5, max_lv))
        for k, (tr, te) in enumerate(gkf.split(P, y, groups)):
            pls = PLSRegression(max_lv, scale=False).fit(P[tr], y[tr])
            t = (P[te] - pls._x_mean) @ pls.x_rotations_
            pred = pls._y_mean[0] + np.cumsum(t * pls.y_loadings_[0], axis=1)
            errs[k] = np.sqrt(((pred - y[te, None]) ** 2).mean(axis=0))
        mean, se = errs.mean(0), errs.std(0, ddof=1) / np.sqrt(5)
        i = int(np.argmin(mean))
        a = int(np.argmax(mean <= mean[i] + se[i])) + 1
        if best is None or mean[a - 1] < best[2]:
            best = (kind, a, float(mean[a - 1]))
    return best


def fit_predict(Xtr, ytr, gtr, Xte):
    kind, a, cv = choose(Xtr, ytr, gtr)
    pls = PLSRegression(a, scale=False).fit(preprocess(Xtr, kind), ytr)
    return pls.predict(preprocess(Xte, kind)).ravel(), {"preprocessing": kind, "n_lv": a, "cv_rmse": cv}


def run() -> dict:
    df = load()
    df = df[df.ethanol <= 90].reset_index(drop=True)  # neat ethanol is outside the blend range
    X = np.vstack(df.spectrum.to_numpy())
    y = df.ethanol.to_numpy(float)
    # group = base composition: blends of the same base fuel at different ethanol levels stay together
    base = df.id.str.replace(r"-E\d+$|-\d+$", "", regex=True).str.replace(r"E\d+$", "", regex=True)
    groups = pd.factorize(base)[0]
    out: dict = {"data_label": "REAL DATA (lab-prepared blends)", "instrument": "FTIR-ATR (OSU)",
                 "n_samples": int(len(df)), "n_with_ethanol": int((y > 0).sum()),
                 "families": df.family.value_counts().to_dict(), "ethanol_levels": sorted(set(y.tolist()))}

    # 1. grouped 10-fold CV (selection nested inside every fold)
    oof = np.zeros_like(y)
    for tr, te in GroupKFold(10).split(X, y, groups):
        oof[te], _ = fit_predict(X[tr], y[tr], groups[tr], X[te])
    band = (y >= 15) & (y <= 25)
    out["grouped_cv"] = {"all": metrics(y, oof), "E15-E25": metrics(y[band], oof[band]),
                         "E0-E30": metrics(y[y <= 30], oof[y <= 30])}

    # 2. leave-one-family-out
    lofo = {}
    for fam in df.family.unique():
        te = (df.family == fam).to_numpy()
        if te.sum() < 4 or fam == "ethanol-free hydrocarbons":
            continue
        p, info = fit_predict(X[~te], y[~te], groups[~te], X[te])
        lofo[fam] = {**metrics(y[te], p), **info}
    out["leave_one_family_out"] = lofo

    # 3. leave-E20-out: no 20 % sample in training at all
    e20 = y == 20
    p20, info20 = fit_predict(X[~e20], y[~e20], groups[~e20], X[e20])
    out["leave_E20_out"] = {**metrics(y[e20], p20), **info20, "n": int(e20.sum()),
                            "pred_mean": float(p20.mean()), "pred_sd": float(p20.std(ddof=1))}

    # final model on everything (for the site's parity plot)
    pall, info = fit_predict(X, y, groups, X)
    out["final_model"] = info
    out["parity"] = {"ref": y.tolist(), "oof": oof.round(3).tolist(), "family": df.family.tolist(), "id": df.id.tolist()}
    out["e20_parity"] = {"ref": y[e20].tolist(), "pred": p20.round(3).tolist(), "id": df.id[e20].tolist()}
    i_e20 = int(np.argmax(y == 20))
    i_e0 = int(np.argmax(y == 0))
    out["example_spectra"] = {"wavenumber": GRID[::4].tolist(), "E0": X[i_e0, ::4].round(5).tolist(), "E0_id": df.id[i_e0],
                              "E20": X[i_e20, ::4].round(5).tolist(), "E20_id": df.id[i_e20]}

    (SITE_DATA / "validation").mkdir(parents=True, exist_ok=True)
    dump({k: v for k, v in out.items() if k not in ("parity", "example_spectra")}, ARTEFACTS / "validation_ftir.json", indent=1)
    dump(out, SITE_DATA / "validation" / "ftir.json")
    return out


if __name__ == "__main__":
    o = run()
    print(o["n_samples"], "samples,", o["n_with_ethanol"], "with ethanol;", o["families"])
    for k, v in o["grouped_cv"].items():
        print(f"grouped CV {k:8s} R2={v['r2']:.3f} RMSEP={v['rmsep']:.2f} bias={v['bias']:+.2f} RPD={v['rpd']:.1f} n={v['n']}")
    for k, v in o["leave_one_family_out"].items():
        print(f"LOFO {k:42s} n={v['n']:3d} RMSEP={v['rmsep']:.2f} bias={v['bias']:+.2f} ({v['preprocessing']}, {v['n_lv']} LV)")
    v = o["leave_E20_out"]
    print(f"leave-E20-out n={v['n']} RMSEP={v['rmsep']:.2f} bias={v['bias']:+.2f} mean pred={v['pred_mean']:.2f}±{v['pred_sd']:.2f}")
