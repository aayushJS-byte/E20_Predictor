# E20 water-ingress early warning

A two-layer early-warning system for water ingress in India's E20 fuel supply chain, built for the
Chemical Engineering second progress review, plus a static walkthrough website.

- **Layer A: depot check (REAL DATA).** Raman spectrum of a tanker sample → PLS regression → ethanol and
  water content with a 95 % prediction interval → PASS / REVIEW / FAIL. Trained and tested on the public
  [FuelRamanSpectraHandheld](https://huggingface.co/datasets/HTW-KI-Werkstatt/FuelRamanSpectraHandheld)
  dataset (179 real gasolines, CC-BY-4.0).
- **Layer B: retail-tank forecast (SYNTHETIC, physics-informed).** A tank simulator driven by real ERA5
  weather for Varanasi produces gauge telemetry; forecasters predict the *margin to separation* 6–72 h
  ahead and raise SAFE / WATCH / ACT alerts; change-point detectors watch the gauge streams.
- **Solution 4 (drain-out routine)** is simulated as a controlled experiment (same tank and weather, drain on vs off).

The website runs the real PLS model and the simulator **in the browser**; Python only writes JSON.

## What is real and what is not

| Item | Label | Notes |
|---|---|---|
| Raman spectra, ethanol and water reference values | **REAL DATA** | handheld IDRaman mini 2.0, 785 nm, 400–2300 cm⁻¹; European E0–E10 gasolines |
| Layer A metrics | **REAL DATA** | held-out test split (36 samples), scored once |
| Weather (temperature, RH, rain, soil temperature) | **REAL DATA (ERA5 reanalysis)** | Open-Meteo archive API, Varanasi 2022–2024 |
| Water tolerance of E20 vs temperature | **LITERATURE VALUE** | US 8,268,629 B2 col. 10 correlation, cross-checked against EPA (1995) and Haq & Ali (1990) |
| Specification limits | **STANDARD** | IS 15464:2004, IS 17943:2022, EN 228 |
| Tanks, leaks, deliveries, gauges, incidents; all Layer B metrics | **SYNTHETIC (physics-informed)** | depends on values marked ASSUMPTION in `config/constants.yaml` |

**Two different water limits.** The original repo's "0.5 % / 5,000 ppm" is the IS 15464:2004 definition of
absolute alcohol: water in *neat ethanol* before blending (clause 3.2). The *blend* quality limit is
0.050 % v/v (≈ 665 mg/kg, IS 17943:2022 Table 1 row xix). The *phase-separation* point of E20 is about
1.4–2.0 wt % between 0 and 30 °C. All three are separate named constants.

**NIR vs Raman.** The proposal says NIR; the public dataset is Raman. Both are vibrational spectroscopy and
both are calibrated with PLS. For water, NIR (O–H overtones) is the better tool; see the results.

## Results

### Layer A (REAL DATA, held-out test set, n = 36)

| Target | Pipeline (chosen by 10-fold CV on train + val) | LVs | R² | RMSEP | SEP | bias | RPD |
|---|---|---|---|---|---|---|---|
| Ethanol, % v/v | ALS baseline + SNV, 400–1800 cm⁻¹ | 5 | 0.948 | 0.70 | 0.67 | −0.22 | 4.6 |
| Ethanol, ridge baseline | same | – | 0.950 | 0.68 | 0.67 | −0.16 | 4.6 |
| Water, mg/kg* | SG 2nd derivative + SNV, 400–1800 cm⁻¹ | 1 | 0.27 | 191 | 193 | +17 | 1.17 |
| Water from lab ethanol alone | linear | – | 0.25 | 193 | 196 | −0.3 | 1.16 |

\* units are not stated on the dataset card; values (40–1,700) are consistent with mg/kg.

**The water model does not work**, and the reason is physical. It does no better than predicting water from
the lab ethanol value (water and ethanol correlate, r = 0.58). The O–H stretch lies outside the
instrument's range, and the samples hold 40–1,700 mg/kg, far below E20's ~15,000 mg/kg separation point.
**The ethanol model was calibrated only on 0–10 % v/v**, and ethanol is strongly anti-correlated with ETBE
in this dataset, so it must be recalibrated on Indian E20 before use.

### Layer B (SYNTHETIC; depends on ASSUMPTION values)

Run `make layer-b` and see `artefacts/layer_b_metrics.json` or section 8 of the site for the current numbers.
The headline comparison on the 2024 test fleet (80 tanks, trained on 2022–23 weather) is:

| Model | margin MAE 24 h / 72 h | incidents with ACT before onset | median lead | ACT precision |
|---|---|---|---|---|
| (a) original repo XGBoost | 0.034 / 0.051 | 0 / 20 | – | – |
| (b) gradient-boosted, lagged + forecast features | 0.018 / 0.031 | 16 / 20 | 42 h | 69 % |
| (c) physics roll-forward | 0.016 / 0.033 | 8 / 20 | 46 h | 51 % |

Other findings: breathing alone never separates E20 in the simulator (it adds tens to hundreds of grams per day
against a tolerance above 100 kg), which agrees with EPA (Korotney 1995). Liquid water through faulty seals
and wet tankers is what matters. Weekly drain-outs cut the number of major-leak tanks that separate from
69 to 13 of 70; how large that effect is depends on the assumed dissolution rate of settled water.
Change-point detection on the water float: F1 ≈ 0.62. Volume reconciliation (gauge − book) *detects*
new separations within ~1.5 h but cannot forecast them.

**To validate Layer B on real tanks** we need OMC ATG logs (30-min product level, water float, temperature),
delivery records, daily water checks and, above all, drain-out records with measured water volume, plus
seal-inspection findings, over at least one monsoon.

## Validation (`make validate`, `validation/`)

Every claim is tested more than one way, on every public dataset we could find. No public tank-gauge
data with water ingress exists, and no public spectra of commercial E20 exist; both gaps are stated.

| Check | Data | Result |
|---|---|---|
| Ethanol by Raman, 10× repeated nested 5-fold CV (selection inside every fold) | REAL, 164 samples | **±0.92 ± 0.02 % v/v**, R² 0.92 |
| Bootstrap 95 % CI, held-out test | REAL | R² 0.92–0.97 |
| Y-randomisation, 200 permutations | REAL | p = 0.005 (chance error ≈ 3.2 vs 0.70) |
| 95 % prediction-interval coverage | REAL | 94 % (nested CV), 97 % (test) |
| PLS vs ridge / SVR / random forest / gradient boosting | REAL | all ±0.68–0.70 except GBM ±1.09 |
| Error by grade (nested CV) | REAL | E0 ±0.53, E5 ±1.00, E10 ±1.07 (grows with ethanol) |
| Other properties from the same spectra | REAL | RPD ETBE 4.6, MTBE 5.1, benzene 3.7, RON 3.4, aromatics 2.7 |
| **Ethanol at E20 by FTIR**, every 20 % blend removed from training | REAL lab blends (Zenodo 21245871) | 22 unseen E20 blends predicted at **20.8 ± 1.3 %** |
| FTIR grouped CV, 0–90 % ethanol | REAL lab blends, 210 spectra | R² 0.984, ±3.2 % v/v; ±1.6 in E15–E25 |
| Water-tolerance curve vs 33 measurements | Johansen & Schramm 2009, EPA/API E10 curve, Haq & Ali 1990 | E10 curve: 5 % error; E5–E30: 15 %, slightly low near E20 (conservative) |
| Layer B on 5 other cities' real 2024 weather, trained on Varanasi only | SYNTHETIC tanks, REAL weather | medians: GBM catches 83 % / 46 % alerts right; physics 64 % / 69 %; both-agree ensemble 40 % / 90 % |
| Layer B with assumptions deliberately wrong (dissolution ×0.5/×2, leaks ×0.5/×2, 3× noisier water test, lower-phase composition, +15 % tolerance) | SYNTHETIC | GBM keeps recall (88–100 %) but over-alerts when leaks are larger; physics keeps precision |

Findings that change the recommendation: the gradient-boosted model over-alerts in climates wetter than its
training data (Mumbai: 7 % of ACT alerts right), so ACT alerts should come from the physics model or the
both-agree ensemble, with the GBM used for WATCH.

## Repository layout

```text
config/constants.yaml     every constant, limit and assumption, each with a source (or ASSUMPTION)
config/references.bib     bibliography used by the site's Assumptions page
common/                   config loader, sourced physics, site-metadata export
layer_a/                  load.py · preprocess.py · pls.py · conformity.py · export.py
sim/                      tank.py (simulator) · weather.py (ERA5 via Open-Meteo, synthetic fallback)
layer_b/                  dataset.py · physics_forecast.py · models.py · changepoint.py · run.py
tests/                    pytest suite + fixtures shared with the JS tests
site/                     Vite + TypeScript + D3 static site (reads site/public/data/*.json)
legacy/                   the original Streamlit dashboard, unchanged
run_all.py, Makefile      regenerate everything
```

## How to run

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make all        # dataset → Layer A → Layer B → site JSON → tests → site build (~15 min)
make test       # ruff + pytest + vitest
make preview    # build and serve the site at http://localhost:4173
```

Or step by step: `python -m layer_a.load`, `python -m layer_a.export`, `python -m layer_b.run`,
`python -m common.site_meta`, then `cd site && npm ci && npm run dev`.

Tests check that the simulator's water mass balance closes (to 1e-6 kg), the tolerance curve is monotonic
and matches the literature check points, the train/validation/test splits are disjoint, Layer B features
use only past observables, and that the browser PLS and simulator reproduce Python to < 1e-6.

The legacy dashboard still runs: `cd legacy && pip install -r requirements.txt && streamlit run app.py`.

## Deploying the site

`.github/workflows/pages.yml` runs the Python tests, the JS equivalence tests, builds `site/` and publishes
it to GitHub Pages on every push to `main`. In the repository settings, set **Pages → Source → GitHub
Actions**. The site is fully static; the generated JSON in `site/public/data/` is committed, so CI does not
rerun the 15-minute pipeline.

## Citations and licences

- Dataset: HTW-KI-Werkstatt, *FuelRamanSpectraHandheld*, Hugging Face, **CC-BY-4.0**. Cite
  Legner et al., *Energy & Fuels* 34 (2020) 103–110, doi:10.1021/acs.energyfuels.9b02944, and
  Voigt et al., *Fuel* 236 (2019) 829–835, doi:10.1016/j.fuel.2018.09.006.
- Weather: ERA5 (Hersbach et al. 2020, Copernicus C3S) via the Open-Meteo historical API, CC-BY-4.0.
- Water tolerance: Coleman, Wolf & Bruya, US 8,268,629 B2 (2012); French & Malone, *Fluid Phase Equilibria*
  228–229 (2005) 27–40; Haq & Ali, *Pak. J. Sci. Ind. Res.* 33 (1990) 351–353; Korotney, US EPA memo (1995).
- Standards: BIS IS 15464:2004, IS 17943:2022; CEN EN 228.
- Full list: `config/references.bib` and section 9 of the site.
