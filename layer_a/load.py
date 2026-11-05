"""Load the FuelRamanSpectraHandheld dataset and save tidy parquet files.

Dataset: HTW-KI-Werkstatt/FuelRamanSpectraHandheld (CC-BY-4.0), 179 gasoline
samples, handheld IDRaman mini 2.0, 785 nm. Citations: Legner et al. 2020
(Energy & Fuels, doi:10.1021/acs.energyfuels.9b02944) and Voigt et al. 2019
(Fuel, doi:10.1016/j.fuel.2018.09.006).

Spectral columns are identified by parsing the column header as a wavenumber;
everything else is a reference (target) value. Targets are never imputed.
"""

from __future__ import annotations

import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from common.config import ROOT

HUB_ID = "HTW-KI-Werkstatt/FuelRamanSpectraHandheld"
HUB_FILES = {"train": "train.parquet", "validation": "val.parquet", "test": "test.parquet"}
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

TARGET_ETHANOL = "Ethanol Content (%)"
TARGET_WATER = "Water Content"


def _cafile():
    try:
        import certifi

        return certifi.where()
    except ImportError:
        return None


@dataclass
class RamanData:
    X: np.ndarray            # (n_samples, n_wavenumbers) raw intensities
    wavenumbers: np.ndarray  # (n_wavenumbers,) cm^-1
    targets: pd.DataFrame    # reference values, NaN where not measured
    split: np.ndarray        # "train" | "validation" | "test"
    sample_id: np.ndarray    # stable id, e.g. "test-007"


def _download_raw() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for fname in HUB_FILES.values():
        dest = RAW_DIR / fname
        if dest.exists() and dest.stat().st_size > 0:
            continue
        url = f"https://huggingface.co/datasets/{HUB_ID}/resolve/main/{fname}"
        print(f"downloading {url}")
        ctx = ssl.create_default_context(cafile=_cafile())
        with urllib.request.urlopen(url, timeout=300, context=ctx) as r:
            dest.write_bytes(r.read())


def _load_splits() -> dict[str, pd.DataFrame]:
    """Load the three splits with the `datasets` library.

    The raw parquet files are fetched once into data/raw/ (the hub metadata
    calls of `load_dataset(HUB_ID)` were observed to stall on slow links), then
    read through `datasets.load_dataset("parquet", ...)`.
    """
    from datasets import load_dataset

    _download_raw()
    files = {split: str(RAW_DIR / f) for split, f in HUB_FILES.items()}
    ds = load_dataset("parquet", data_files=files)
    return {split: ds[split].to_pandas() for split in HUB_FILES}


def _is_wavenumber(col: str) -> bool:
    try:
        float(col)
        return True
    except ValueError:
        return False


def split_columns(columns) -> tuple[list[str], list[str]]:
    spectral = [c for c in columns if _is_wavenumber(c)]
    targets = [c for c in columns if not _is_wavenumber(c)]
    return spectral, targets


def build() -> RamanData:
    frames = _load_splits()
    parts = []
    for split, df in frames.items():
        df = df.copy()
        df.insert(0, "split", split)
        prefix = {"train": "train", "validation": "val", "test": "test"}[split]
        df.insert(0, "sample_id", [f"{prefix}-{i:03d}" for i in range(len(df))])
        parts.append(df)
    full = pd.concat(parts, ignore_index=True)
    spectral, target_cols = split_columns(full.columns.drop(["sample_id", "split"]))
    wn = np.array([float(c) for c in spectral])
    order = np.argsort(wn)
    spectral = [spectral[i] for i in order]
    return RamanData(
        X=full[spectral].to_numpy(dtype=float),
        wavenumbers=wn[order],
        targets=full[target_cols].reset_index(drop=True),
        split=full["split"].to_numpy(),
        sample_id=full["sample_id"].to_numpy(),
    )


def save_tidy(data: RamanData, out_dir: Path = PROCESSED_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    samples = data.targets.copy()
    samples.insert(0, "split", data.split)
    samples.insert(0, "sample_id", data.sample_id)
    samples.to_parquet(out_dir / "samples.parquet", index=False)
    long = pd.DataFrame(
        {
            "sample_id": np.repeat(data.sample_id, len(data.wavenumbers)),
            "wavenumber_cm1": np.tile(data.wavenumbers, len(data.sample_id)),
            "intensity": data.X.ravel(),
        }
    )
    long.to_parquet(out_dir / "spectra_long.parquet", index=False)


def load() -> RamanData:
    """Load from data/processed if present, else build from the hub."""
    s, sp = PROCESSED_DIR / "samples.parquet", PROCESSED_DIR / "spectra_long.parquet"
    if not (s.exists() and sp.exists()):
        data = build()
        save_tidy(data)
        return data
    samples = pd.read_parquet(s)
    long = pd.read_parquet(sp)
    wide = long.pivot(index="sample_id", columns="wavenumber_cm1", values="intensity")
    wide = wide.loc[samples["sample_id"]]
    return RamanData(
        X=wide.to_numpy(dtype=float),
        wavenumbers=wide.columns.to_numpy(dtype=float),
        targets=samples.drop(columns=["sample_id", "split"]),
        split=samples["split"].to_numpy(),
        sample_id=samples["sample_id"].to_numpy(),
    )


if __name__ == "__main__":
    d = build()
    save_tidy(d)
    print(f"{len(d.sample_id)} samples x {len(d.wavenumbers)} wavenumbers "
          f"({d.wavenumbers[0]:.0f}-{d.wavenumbers[-1]:.0f} cm-1)")
    print(pd.Series(d.split).value_counts().to_dict())
    print(d.targets.notna().sum().to_dict())
