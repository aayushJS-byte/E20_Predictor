"""Spectral preprocessing as scikit-learn transformers.

Every transformer is implemented in plain numpy with fully specified edge
handling, so the exact same arithmetic can be reproduced in the browser
(site/src/lib/pls.ts). Each transformer exposes `export()` -> JSON-able dict.

Steps:
  Crop       - keep a wavenumber window
  ALS        - asymmetric least squares baseline removal (Eilers & Boelens 2005)
  SavGol     - Savitzky-Golay smoothing / derivative (edge-replicate padding)
  SNV        - standard normal variate (per spectrum)
  MSC        - multiplicative scatter correction against the training mean
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import solveh_banded
from scipy.signal import savgol_coeffs
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline


class Crop(BaseEstimator, TransformerMixin):
    def __init__(self, wavenumbers=None, lo=400.0, hi=2300.0):
        self.wavenumbers = wavenumbers
        self.lo = lo
        self.hi = hi

    def fit(self, X, y=None):
        wn = np.asarray(self.wavenumbers)
        self.mask_ = (wn >= self.lo) & (wn <= self.hi)
        self.start_ = int(np.argmax(self.mask_))
        self.stop_ = int(self.start_ + self.mask_.sum())
        return self

    def transform(self, X):
        return np.asarray(X, dtype=float)[:, self.start_:self.stop_]

    def export(self):
        return {"type": "crop", "start": self.start_, "stop": self.stop_, "lo": self.lo, "hi": self.hi}


def als_baseline(y: np.ndarray, lam: float, p: float, n_iter: int) -> np.ndarray:
    """Eilers & Boelens (2005) asymmetric least squares baseline.

    Solves (W + lam * D'D) z = W y with D the second-difference operator,
    using a symmetric banded (pentadiagonal) Cholesky solve.
    """
    n = y.size
    # upper banded storage of D'D (bandwidth 2)
    dtd = np.zeros((3, n))
    main = np.full(n, 6.0)
    main[[0, -1]] = 1.0
    main[[1, -2]] = 5.0
    off1 = np.full(n - 1, -4.0)
    off1[[0, -1]] = -2.0
    off2 = np.ones(n - 2)
    dtd[2] = main
    dtd[1, 1:] = off1
    dtd[0, 2:] = off2
    dtd *= lam
    w = np.ones(n)
    z = y
    for _ in range(n_iter):
        ab = dtd.copy()
        ab[2] += w
        z = solveh_banded(ab, w * y)
        w = np.where(y > z, p, 1.0 - p)
    return z


class ALS(BaseEstimator, TransformerMixin):
    def __sklearn_is_fitted__(self):
        return True

    def __init__(self, lam=1e6, p=0.01, n_iter=10):
        self.lam = lam
        self.p = p
        self.n_iter = n_iter

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        return np.vstack([row - als_baseline(row, self.lam, self.p, self.n_iter) for row in X])

    def export(self):
        return {"type": "als", "lam": self.lam, "p": self.p, "n_iter": self.n_iter}


class SavGol(BaseEstimator, TransformerMixin):
    def __init__(self, window=15, polyorder=2, deriv=0):
        self.window = window
        self.polyorder = polyorder
        self.deriv = deriv

    def fit(self, X, y=None):
        # use="dot": coefficient k multiplies x[i - half + k]
        self.coeffs_ = savgol_coeffs(self.window, self.polyorder, deriv=self.deriv, use="dot")
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        half = self.window // 2
        Xp = np.pad(X, ((0, 0), (half, half)), mode="edge")
        out = np.zeros_like(X)
        for k, c in enumerate(self.coeffs_):
            out += c * Xp[:, k:k + X.shape[1]]
        return out

    def export(self):
        return {"type": "savgol", "window": self.window, "polyorder": self.polyorder,
                "deriv": self.deriv, "coeffs": self.coeffs_.tolist()}


class SNV(BaseEstimator, TransformerMixin):
    def __sklearn_is_fitted__(self):
        return True

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        mu = X.mean(axis=1, keepdims=True)
        sd = X.std(axis=1, keepdims=True)  # population std (ddof=0)
        return (X - mu) / sd

    def export(self):
        return {"type": "snv"}


class MSC(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        self.reference_ = np.asarray(X, dtype=float).mean(axis=0)
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        r = self.reference_
        rc = r - r.mean()
        out = np.empty_like(X)
        for i, x in enumerate(X):
            b = np.dot(rc, x - x.mean()) / np.dot(rc, rc)
            a = x.mean() - b * r.mean()
            out[i] = (x - a) / b
        return out

    def export(self):
        return {"type": "msc", "reference": self.reference_.tolist()}


# Candidate preprocessing recipes compared by cross-validation in pls.py.
# Each is a list of (name, factory(wavenumbers)) steps.
RECIPES: dict[str, list] = {
    "raw": [],
    "snv": [("snv", lambda wn: SNV())],
    "msc": [("msc", lambda wn: MSC())],
    "als+snv": [("als", lambda wn: ALS()), ("snv", lambda wn: SNV())],
    "sg-smooth+snv": [("sg", lambda wn: SavGol(11, 2, 0)), ("snv", lambda wn: SNV())],
    "sg-d1": [("sg", lambda wn: SavGol(15, 2, 1))],
    "sg-d1+snv": [("sg", lambda wn: SavGol(15, 2, 1)), ("snv", lambda wn: SNV())],
    "als+sg-smooth+snv": [("als", lambda wn: ALS()), ("sg", lambda wn: SavGol(11, 2, 0)),
                          ("snv", lambda wn: SNV())],
    "sg-d2+snv": [("sg", lambda wn: SavGol(21, 3, 2)), ("snv", lambda wn: SNV())],
}

CROPS: dict[str, tuple[float, float]] = {
    "full 400-2300": (400.0, 2300.0),
    "fingerprint 400-1800": (400.0, 1800.0),
}


def make_preprocessor(recipe: str, crop: str, wavenumbers) -> Pipeline:
    lo, hi = CROPS[crop]
    steps = [("crop", Crop(wavenumbers, lo, hi))]
    steps += [(name, factory(wavenumbers)) for name, factory in RECIPES[recipe]]
    return Pipeline(steps)
