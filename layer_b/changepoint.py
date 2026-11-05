"""Change-point detection on ATG gauge streams (SYNTHETIC evaluation).

Streams (hourly means of the 30-min gauge):
  water level  - float height of the bottom layer (mm)
  recon        - unexplained volume: gauge fuel volume minus book volume (L);
                 ethanol pulled into a lower phase shows up as a loss.

Detectors: water level - ruptures KernelCPD, linear kernel (= l2 mean-shift
cost), penalised (PELT); recon - one-sided CUSUM on 6-h means against a
trailing-median baseline (the ethanol loss is a slow, noisy step). Penalty / threshold chosen on the TRAIN fleet (2022-2023
weather) and evaluated once on the TEST fleet (2024).

Ground truth for the water-level stream: wet-tanker deliveries, rain-ingress
episodes through a faulty seal, drain-outs that removed water, separation
onsets. For the recon stream: separation onsets. A detection within
TOLERANCE_H of a true event is a hit (each event matched at most once).
"""

from __future__ import annotations

import numpy as np
import ruptures as rpt

from layer_b.dataset import TankRun

TOLERANCE_H = 6
MIN_SIZE_H = 3
PENALTIES = [40, 160, 640, 1280, 2560, 5120, 10240, 20480]
CUSUM_H = [8, 32, 128, 256, 512, 1024]
RECON_TOLERANCE_H = 24
HOLDOFF_H = 12  # samples of the recon stream (12 x 6 h = 72 h)
EPISODE_MIN_KG = 2.0


def hourly(x: np.ndarray) -> np.ndarray:
    n = len(x) // 2 * 2
    return x[:n].reshape(-1, 2).mean(axis=1)


def true_events(run: TankRun, stream: str) -> list[int]:
    """Ground-truth change times in hours."""
    ev = []
    if stream == "water":
        for e in run.events:
            if e["type"] == "delivery" and e.get("wet"):
                ev.append(e["step"] // 2)
            elif e["type"] == "drain_out" and e["water_kg"] > EPISODE_MIN_KG:
                ev.append(e["step"] // 2)
            elif e["type"] == "separation_onset":
                ev.append(e["step"] // 2)
        # rain-ingress episodes: first hour of each rainy spell that let in > EPISODE_MIN_KG
        rain = hourly(run.trace["ingress_liquid_kg"].to_numpy()) * 2
        wet = rain > 0
        start = None
        for h, w in enumerate(np.append(wet, False)):
            if w and start is None:
                start = h
            elif not w and start is not None:
                if rain[start:h].sum() > EPISODE_MIN_KG:
                    ev.append(start)
                start = None
    else:
        ev = [e["step"] // 2 for e in run.events if e["type"] == "separation_onset"]
    return sorted(set(ev))


RECON_BLOCK_H = 6


def signal(run: TankRun, stream: str) -> np.ndarray:
    if stream == "water":
        return hourly(run.obs["gauge_water_mm"])
    x = run.obs["recon_L"]
    k = 2 * RECON_BLOCK_H
    n = len(x) // k * k
    return x[:n].reshape(-1, k).mean(axis=1)  # 6-h means: the loss is slow vs gauge noise


def cusum_down(x: np.ndarray, h: float, k_sigma: float = 0.5, ref_n: int = 20) -> list[int]:
    """One-sided CUSUM for a downward level shift (unexplained volume loss).

    Each sample is compared with the median of the preceding `ref_n` samples
    (trailing baseline) and standardised by a robust noise estimate (MAD of
    increments / sqrt 2). An alarm fires when the cumulative sum exceeds h;
    further alarms are held off for HOLDOFF_H samples.
    """
    d = np.diff(x)
    sigma = 1.4826 * float(np.median(np.abs(d - np.median(d)))) / np.sqrt(2) or 1.0
    s, alarms, hold = 0.0, [], -1
    for t in range(ref_n, len(x)):
        ref = float(np.median(x[t - ref_n:t]))
        s = max(0.0, s + (ref - x[t]) / sigma - k_sigma)
        if s > h and t > hold:
            alarms.append(t)
            hold = t + HOLDOFF_H
            s = 0.0
    return alarms


def detect_stream(x: np.ndarray, stream: str, pen: float) -> list[int]:
    """Detected change times in hours."""
    if stream == "water":
        return detect(x, pen)
    return [t * RECON_BLOCK_H for t in cusum_down(x, pen)]


def detect(x: np.ndarray, pen: float) -> list[int]:
    # KernelCPD with a linear kernel == l2 (mean-shift) cost, solved by PELT in C
    algo = rpt.KernelCPD(kernel="linear", min_size=MIN_SIZE_H).fit(x.reshape(-1, 1))
    scale = float(np.var(np.diff(x))) / 2 or 1.0  # noise variance estimate -> penalty in noise units
    bkps = algo.predict(pen=pen * scale)
    return [b for b in bkps[:-1]]


def match(detected: list[int], truth: list[int], tol: int = TOLERANCE_H) -> tuple[int, int, int, list[int]]:
    used = set()
    tp, delays = 0, []
    for t in truth:
        cands = [d for d in detected if abs(d - t) <= tol and d not in used]
        if cands:
            d = min(cands, key=lambda d: abs(d - t))
            used.add(d)
            tp += 1
            delays.append(d - t)
    return tp, len(detected) - tp, len(truth) - tp, delays


def score(runs: list[TankRun], stream: str, pen: float) -> dict:
    tp = fp = fn = 0
    delays = []
    for r in runs:
        x = signal(r, stream)
        tol = TOLERANCE_H if stream == "water" else RECON_TOLERANCE_H
        det = detect_stream(x, stream, pen)
        if stream == "recon":
            # The question for this stream is "does it reveal a NEW separation?". Alarms
            # raised while a lower phase already existed (more than `tol` h after it
            # formed) flag real, ongoing losses; they are ignored, not counted as false.
            sep = hourly(r.trace["lower_water_kg"].to_numpy()) > 0
            det = [t for t in det if not sep[max(0, min(len(sep) - 1, t - tol))]]
        a, b, c, d = match(det, true_events(r, stream), tol)
        tp, fp, fn = tp + a, fp + b, fn + c
        delays += d
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else 0.0
    return {"penalty": pen, "tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec, "f1": f1,
            "mean_abs_delay_h": float(np.mean(np.abs(delays))) if delays else None}


def tune_and_test(train: list[TankRun], test: list[TankRun], stream: str) -> dict:
    grid = PENALTIES if stream == "water" else CUSUM_H
    sweep = [score(train, stream, pen) for pen in grid]
    best = max(sweep, key=lambda s: s["f1"])
    return {"stream": stream, "train_sweep": sweep, "chosen_penalty": best["penalty"],
            "test": score(test, stream, best["penalty"]),
            "detector": "KernelCPD linear (PELT)" if stream == "water" else "one-sided CUSUM on volume loss",
            "tolerance_h": TOLERANCE_H if stream == "water" else RECON_TOLERANCE_H}
