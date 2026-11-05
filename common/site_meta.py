"""Export constants.yaml, references.bib and run metadata as JSON for the site.

The site's "Assumptions & sources" page is generated from these files, so it
can never drift from the numbers the code actually uses.
"""

from __future__ import annotations

import json
import platform
import re
from importlib import metadata

from common.config import ROOT, SITE_DATA, constants, iter_entries

PACKAGES = ["numpy", "scipy", "pandas", "scikit-learn", "xgboost", "ruptures", "datasets", "pyyaml"]


def parse_bib(text: str) -> list[dict]:
    entries = []
    for m in re.finditer(r"@(\w+)\{([^,]+),(.*?)\n\}", text, re.S):
        kind, key, body = m.group(1), m.group(2).strip(), m.group(3)
        fields = {}
        for f in re.finditer(r"(\w+)\s*=\s*\{(.*?)\}\s*,?\s*$", body, re.M | re.S):
            val = re.sub(r"\s+", " ", f.group(2)).replace("{", "").replace("}", "").replace("\\&", "&")
            val = re.sub(r"\\url", "", val)
            fields[f.group(1).lower()] = val.strip()
        entries.append({"key": key, "type": kind, **fields})
    return entries


def main() -> None:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    c = constants()
    rows = []
    for key, e in iter_entries():
        rows.append({"key": key, "value": e.get("value", {k: e[k] for k in ("a", "b", "c", "form") if k in e}),
                     "unit": e.get("unit"), "source": e.get("source"), "label": e.get("label"),
                     "note": (e.get("note") or "").strip() or None})
    meta = {
        "python": platform.python_version(),
        "packages": {p: metadata.version(p) for p in PACKAGES},
        "seeds": {"layer_a_cv": 0, "fleet": "per tank: int(year) * 100 + k", "gbm": 0},
        "dataset": "https://huggingface.co/datasets/HTW-KI-Werkstatt/FuelRamanSpectraHandheld",
    }
    (SITE_DATA / "constants.json").write_text(json.dumps(c))
    (SITE_DATA / "sources.json").write_text(json.dumps({
        "entries": rows,
        "references": parse_bib((ROOT / "config" / "references.bib").read_text()),
        "meta": meta,
    }))
    n_ass = sum(r["label"] == "ASSUMPTION" for r in rows)
    print(f"wrote constants.json and sources.json ({len(rows)} entries, {n_ass} ASSUMPTION)")


if __name__ == "__main__":
    main()
