"""Fit Layer A, then write every artefact the website and the tests need.

Outputs
  site/public/data/layer_a/model_<target>.json   in-browser model (preprocessing + PLS)
  site/public/data/layer_a/results.json          metrics, CV curves, parity, VIP, bands
  site/public/data/layer_a/test_spectra.json     held-out test spectra (REAL DATA)
  tests/fixtures/pls_reference.json              Python predictions for the JS equivalence test
  artefacts/figures/layer_a_*.png                static figures for the report
"""

from __future__ import annotations

import json

import numpy as np

from common.config import ARTEFACTS, ROOT, SITE_DATA
from layer_a.conformity import check, grade_limits
from layer_a.load import TARGET_ETHANOL, TARGET_WATER, load
from layer_a.pls import export_model, prediction_interval, run, vip_scores

OUT = SITE_DATA / "layer_a"
FIXTURES = ROOT / "tests" / "fixtures"
SPECTRUM_DECIMALS = 3

# Only bands with a citation are annotated.
BANDS = [
    {"wavenumber": 885, "label": "ethanol C–C–O symmetric stretch", "range": [875, 895],
     "source": "jain2025 (~885 cm-1); aipadv2020 (888.8 cm-1)"},
    {"wavenumber": 1005, "label": "aromatic ring breathing (gasoline aromatics)", "range": [995, 1012],
     "source": "jain2025 (~1005 cm-1)"},
]


def _r(a, d=6):
    return np.round(np.asarray(a, dtype=float), d).tolist()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (ARTEFACTS / "figures").mkdir(parents=True, exist_ok=True)

    data = load()
    fitted = run()
    test = data.split == "test"
    X_test = np.round(data.X[test], SPECTRUM_DECIMALS)
    ids = data.sample_id[test]
    limits = grade_limits()

    # ---- test spectra for the site ---------------------------------------
    eth = data.targets[TARGET_ETHANOL].to_numpy(dtype=float)[test]
    wat = data.targets[TARGET_WATER].to_numpy(dtype=float)[test]
    spectra = {
        "data_label": "REAL DATA",
        "source": "HTW-KI-Werkstatt/FuelRamanSpectraHandheld (CC-BY-4.0), test split",
        "wavenumbers": data.wavenumbers.tolist(),
        "samples": [
            {"id": sid, "ethanol_ref": None if np.isnan(e) else float(e),
             "water_ref": None if np.isnan(w) else float(w), "spectrum": x.tolist()}
            for sid, e, w, x in zip(ids, eth, wat, X_test, strict=True)
        ],
    }
    (OUT / "test_spectra.json").write_text(json.dumps(spectra))

    results = {"data_label": "REAL DATA", "bands": BANDS, "limits": limits, "targets": {}}
    fixture = {"wavenumbers": data.wavenumbers.tolist(), "cases": []}
    rng = np.random.default_rng(0)
    perturbed = {
        "raw": X_test,
        "noise": X_test + np.round(rng.normal(0, 200, X_test.shape), SPECTRUM_DECIMALS),
        "baseline": X_test + np.round(np.linspace(0, 3000, X_test.shape[1]), SPECTRUM_DECIMALS),
    }

    for target, (model, res) in fitted.items():
        exp = export_model(model, data.wavenumbers)
        (OUT / f"model_{target}.json").write_text(json.dumps(exp))

        # dev-set latent-variable scores for the projection plot
        t_dev = model.pls.x_scores_
        lv = {"t1": _r(t_dev[:, 0], 4),
              "t2": _r(t_dev[:, 1], 4) if t_dev.shape[1] > 1 else None,
              "y": _r(res["dev_ref"], 3)}
        pred, half, h, q = prediction_interval(model, X_test)
        res["test_pi_half"] = _r(half, 4)
        res["test_leverage"] = _r(h, 5)
        res["test_q"] = _r(q, 3)
        res["test_pred"] = _r(pred, 5)
        res["lv_scores_dev"] = lv
        res["vip"] = _r(vip_scores(model.pls), 4)
        res["coef"] = _r(exp["beta"], 8)
        res["wavenumbers_model"] = exp["wavenumbers_model"]
        res["top_vip_wavenumbers"] = [float(w) for w in np.array(exp["wavenumbers_model"])[np.argsort(-np.array(res["vip"]))[:15]]]
        lo, hi = (limits["E10"]["ethanol"] if target == "ethanol"
                  else [0.0, limits["water_max_mg_per_kg"]["value"]])
        res["conformity_demo"] = {"declared_grade": "E10" if target == "ethanol" else "E20 water limit",
                                  "limits": [lo, hi],
                                  "checks": [dict(check(model, x, lo, hi), id=sid)
                                             for sid, x in zip(ids, X_test, strict=True)]}
        for k in ("dev_fitted",):
            res.pop(k, None)
        results["targets"][target] = res

        for kind, Xk in perturbed.items():
            p, hw, hh, qq = prediction_interval(model, Xk)
            for i in range(0, len(Xk), 6):
                fixture["cases"].append({"target": target, "kind": kind, "id": ids[i],
                                         "spectrum": Xk[i].tolist(), "pred": float(p[i]),
                                         "half": float(hw[i]), "h": float(hh[i]), "q": float(qq[i])})

    (OUT / "results.json").write_text(json.dumps(results))
    (FIXTURES / "pls_reference.json").write_text(json.dumps(fixture))
    _figures(results)
    print(f"wrote {OUT}")


def _figures(results: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for target, res in results["targets"].items():
        fig, ax = plt.subplots(1, 3, figsize=(15, 4.5))
        ref, pred = np.array(res["test_ref"]), np.array(res["test_pred"])
        lim = [min(ref.min(), pred.min()), max(ref.max(), pred.max())]
        ax[0].plot(lim, lim, color="#999", lw=1)
        ax[0].errorbar(ref, pred, yerr=res["test_pi_half"], fmt="o", ms=4, alpha=0.7, elinewidth=0.6)
        m = res["test"]["pls"]
        ax[0].set_title(f"{target} – test parity (R²={m['r2']:.2f}, RMSEP={m['rmsep']:.3g})\nREAL DATA")
        ax[0].set_xlabel("reference")
        ax[0].set_ylabel("predicted")
        cv = np.array(res["selection"]["cv_curve"])
        ax[1].errorbar(np.arange(1, len(cv) + 1), cv, yerr=res["selection"]["cv_curve_se"], marker="o", ms=3)
        ax[1].axvline(res["selection"]["n_lv"], color="k", ls="--", lw=1)
        ax[1].set_title("RMSECV vs latent variables (train+val, 10-fold)")
        ax[1].set_xlabel("latent variables")
        wn = res["wavenumbers_model"]
        ax[2].plot(wn, res["vip"], lw=1)
        for b in results["bands"]:
            ax[2].axvline(b["wavenumber"], color="#c33", lw=0.8, ls=":")
            ax[2].text(b["wavenumber"], max(res["vip"]) * 0.95, b["label"], rotation=90, fontsize=7, va="top")
        ax[2].axhline(1, color="#999", lw=0.8)
        ax[2].set_title("VIP over wavenumber")
        ax[2].set_xlabel("Raman shift / cm⁻¹")
        fig.tight_layout()
        fig.savefig(ARTEFACTS / "figures" / f"layer_a_{target}.png", dpi=130)
        plt.close(fig)


if __name__ == "__main__":
    main()
