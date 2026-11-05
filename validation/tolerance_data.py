"""Measured water-tolerance data used to validate the tolerance correlation (LITERATURE VALUE).

Sources (all measurements, none generated here):
  johansen2009  Johansen & Schramm, Energy Sources A 31 (2009) 1634-1645, Appendix II,
                Tables II-1 (-2 C) and II-2 (-25 C): phase-separation points of Euro-95
                gasoline / anhydrous ethanol / water, all in % by mass. Transcribed verbatim.
  korotney1995  US EPA memo (Korotney 1995), Figure 1: water tolerance of E10 vs temperature
                (vol %), citing API Publication 4261 (1988). Extracted from the vector
                drawing commands of the PDF (exact plotted coordinates), not digitised by eye.
  haq1990       Haq & Ali (1990) p. 352-353 text: 25/75 v/v ethanol/gasoline tolerates
                1.78 and 1.88 % mass water at 0 C (the paper states both values).
"""

from __future__ import annotations

import re

import pandas as pd

from common.config import ROOT, value

LIT = ROOT / "data" / "external" / "literature"
EPA_PDF = LIT / "korotney1995.pdf"
EPA_URL = "https://www.epa.gov/sites/default/files/2015-09/documents/waterphs.pdf"

# Johansen & Schramm (2009) Appendix II: (EtOH %, gasoline %, water %) by mass
JOHANSEN_M2 = [(69.65, 7.34, 23.01), (68.55, 16.25, 15.20), (63.90, 25.96, 10.14), (56.75, 35.86, 7.40),
               (48.58, 46.05, 5.38), (39.62, 56.34, 4.40), (30.27, 66.96, 2.77), (20.53, 77.83, 1.64),
               (10.40, 88.74, 0.86), (5.22, 94.05, 0.73)]
JOHANSEN_M25 = [(72.85, 7.67, 19.48), (71.17, 16.87, 11.97), (65.21, 26.49, 8.29), (57.71, 36.47, 5.82),
                (49.09, 46.53, 4.38), (40.10, 57.02, 2.89), (30.43, 67.30, 2.27), (20.59, 78.09, 1.32),
                (10.43, 88.97, 0.60), (5.25, 94.48, 0.27)]


def _ethanol_vol_pct(m_eth: float, m_gas: float) -> float:
    """Ethanol % v/v of the water-free blend, from mass fractions."""
    v_e = m_eth / value("physical", "density_ethanol_20c")
    v_g = m_gas / value("physical", "density_gasoline")
    return 100.0 * v_e / (v_e + v_g)


def johansen() -> pd.DataFrame:
    rows = []
    for t, table in ((-2.0, JOHANSEN_M2), (-25.0, JOHANSEN_M25)):
        for e, g, w in table:
            rows.append({"source": "johansen2009", "temp_c": t, "ethanol_vol_pct": _ethanol_vol_pct(e, g),
                         "ethanol_wt_pct": e, "water_wt_pct": w,
                         "ref": f"Johansen & Schramm 2009, Table II-{1 if t == -2 else 2}"})
    return pd.DataFrame(rows)


def _download_epa() -> None:
    if EPA_PDF.exists():
        return
    import subprocess

    LIT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["curl", "-sL", "--max-time", "120", "-A", "Mozilla/5.0", "-o", str(EPA_PDF), EPA_URL], check=True)


def epa_e10() -> pd.DataFrame:
    """Exact points of the E10 curve in Korotney (1995) Fig. 1, from the PDF vector paths."""
    import pypdf

    _download_epa()
    stream = pypdf.PdfReader(str(EPA_PDF)).pages[1].get_contents().get_data().decode("latin1")
    # the curve is the only green (0 1 0 RG) polyline on the page
    green = stream.split("0 1 0 RG", 1)[1].split("BT", 1)[0]
    pts = re.findall(r"([\d.]+)\s+([\d.]+)\s+m\s+([\d.]+)\s+([\d.]+)\s+l\s+S", green)
    xy = sorted({(float(a), float(b)) for a, b, _, _ in pts} | {(float(c), float(d)) for _, _, c, d in pts})
    # axis calibration from the same drawing: x ticks 177.6 -> -40 F ... 390.72 -> 60 F,
    # y ticks 328.08 -> 0.2 vol % ... 441.36 -> 0.6 vol %
    fx = lambda x: -40.0 + (x - 177.6) * (100.0 / (390.72 - 177.6))  # noqa: E731
    fy = lambda y: 0.2 + (y - 328.08) * (0.4 / (441.36 - 328.08))   # noqa: E731
    rho_w = value("physical", "density_water")
    rho_b = 0.1 * value("physical", "density_ethanol_20c") + 0.9 * value("physical", "density_gasoline")
    rows = []
    for x, y in xy:
        t_f, vv = fx(x), fy(y)
        wt = 100 * vv / 100 * rho_w / (vv / 100 * rho_w + (1 - vv / 100) * rho_b)
        rows.append({"source": "korotney1995", "temp_c": (t_f - 32) / 1.8, "ethanol_vol_pct": 10.0,
                     "water_vol_pct": vv, "water_wt_pct": wt, "ref": "Korotney 1995 (EPA), Fig. 1, after API 4261"})
    return pd.DataFrame(rows)


def haq() -> pd.DataFrame:
    return pd.DataFrame([{"source": "haq1990", "temp_c": 0.0, "ethanol_vol_pct": 25.0, "water_wt_pct": w,
                          "ref": "Haq & Ali 1990, p. 352-353 (text)"} for w in (1.78, 1.88)])


def all_measurements() -> pd.DataFrame:
    return pd.concat([johansen(), epa_e10(), haq()], ignore_index=True)


if __name__ == "__main__":
    df = all_measurements()
    print(df.round(3).to_string())
    out = ROOT / "data" / "external" / "water_tolerance_measurements.csv"
    df.to_csv(out, index=False)
    print("wrote", out)
