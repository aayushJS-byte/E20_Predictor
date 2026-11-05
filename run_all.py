"""Regenerate every artefact from scratch: data -> Layer A -> Layer B -> site JSON.

Usage:  python run_all.py            (about 45 minutes on a laptop)
"""

import subprocess
import sys

STEPS = [
    ("dataset", ["-m", "layer_a.load"]),
    ("layer A: model selection, test metrics, export", ["-m", "layer_a.export"]),
    ("layer B: fleet, forecasts, alerts, change points, twin", ["-m", "layer_b.run"]),
    ("validation: tolerance curve vs 33 measurements", ["-m", "validation.tolerance"]),
    ("validation: Layer A nested CV, bootstrap, permutation, all targets", ["-m", "validation.layer_a_full"]),
    ("validation: FTIR model on 0-90 % ethanol blends", ["-m", "validation.ftir"]),
    ("validation: Layer B other cities and wrong assumptions", ["-m", "validation.layer_b_full"]),
    ("site metadata (constants, sources)", ["-m", "common.site_meta"]),
]

if __name__ == "__main__":
    for name, args in STEPS:
        print(f"\n=== {name} ===", flush=True)
        subprocess.run([sys.executable, *args], check=True)
    print("\nall artefacts regenerated; run `make test` and `cd site && npm run build`.")
