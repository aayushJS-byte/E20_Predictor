// In-browser port of layer_a/preprocess.py + the exported PLS model.
// Arithmetic mirrors the Python implementation step by step; the equivalence
// is checked against Python predictions in tests/pls.test.ts (< 1e-6).

export type Step =
  | { type: "crop"; start: number; stop: number; lo: number; hi: number }
  | { type: "als"; lam: number; p: number; n_iter: number }
  | { type: "savgol"; window: number; polyorder: number; deriv: number; coeffs: number[] }
  | { type: "snv" }
  | { type: "msc"; reference: number[] };

export interface PlsModel {
  target: string;
  unit: string;
  wavenumbers_in: number[];
  wavenumbers_model: number[];
  preprocessing: Step[];
  x_mean: number[];
  beta: number[];
  b0: number;
  x_rotations: number[][]; // (A, p)
  x_loadings: number[][]; // (A, p)
  tt_inv: number[][];
  n_train: number;
  n_lv: number;
  rmsecv: number;
  t_quantile: number;
  pi_level: number;
  q_limit: number;
  h_limit: number;
  calibration_range: [number, number];
  vip: number[];
}

/** Solve the symmetric pentadiagonal system A z = b by banded Cholesky.
 *  A is given by its main diagonal d0, first and second super-diagonals d1, d2. */
export function solvePenta(d0: Float64Array, d1: Float64Array, d2: Float64Array, b: Float64Array): Float64Array {
  const n = d0.length;
  const l0 = new Float64Array(n); // L[i][i]
  const l1 = new Float64Array(n); // L[i][i-1]
  const l2 = new Float64Array(n); // L[i][i-2]
  for (let i = 0; i < n; i++) {
    if (i >= 2) l2[i] = d2[i - 2] / l0[i - 2];
    if (i >= 1) {
      const a = d1[i - 1] - (i >= 2 ? l2[i] * l1[i - 1] : 0);
      l1[i] = a / l0[i - 1];
    }
    const s = d0[i] - l1[i] * l1[i] - l2[i] * l2[i];
    l0[i] = Math.sqrt(s);
  }
  const y = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    let s = b[i];
    if (i >= 1) s -= l1[i] * y[i - 1];
    if (i >= 2) s -= l2[i] * y[i - 2];
    y[i] = s / l0[i];
  }
  const z = new Float64Array(n);
  for (let i = n - 1; i >= 0; i--) {
    let s = y[i];
    if (i + 1 < n) s -= l1[i + 1] * z[i + 1];
    if (i + 2 < n) s -= l2[i + 2] * z[i + 2];
    z[i] = s / l0[i];
  }
  return z;
}

export function alsBaseline(y: Float64Array, lam: number, p: number, nIter: number): Float64Array {
  const n = y.length;
  const main = new Float64Array(n).fill(6);
  main[0] = main[n - 1] = 1;
  main[1] = main[n - 2] = 5;
  const off1 = new Float64Array(n - 1).fill(-4);
  off1[0] = off1[n - 2] = -2;
  const off2 = new Float64Array(n - 2).fill(1);
  for (let i = 0; i < n; i++) main[i] *= lam;
  for (let i = 0; i < n - 1; i++) off1[i] *= lam;
  for (let i = 0; i < n - 2; i++) off2[i] *= lam;
  let w = new Float64Array(n).fill(1);
  let z: Float64Array = y;
  for (let it = 0; it < nIter; it++) {
    const d0 = new Float64Array(n);
    const rhs = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      d0[i] = main[i] + w[i];
      rhs[i] = w[i] * y[i];
    }
    z = solvePenta(d0, off1, off2, rhs);
    const nw = new Float64Array(n);
    for (let i = 0; i < n; i++) nw[i] = y[i] > z[i] ? p : 1 - p;
    w = nw;
  }
  return z;
}

export function applyStep(step: Step, x: Float64Array): Float64Array {
  switch (step.type) {
    case "crop":
      return x.slice(step.start, step.stop);
    case "als": {
      const base = alsBaseline(x, step.lam, step.p, step.n_iter);
      const out = new Float64Array(x.length);
      for (let i = 0; i < x.length; i++) out[i] = x[i] - base[i];
      return out;
    }
    case "savgol": {
      const half = Math.floor(step.window / 2);
      const n = x.length;
      const out = new Float64Array(n);
      for (let k = 0; k < step.coeffs.length; k++) {
        const c = step.coeffs[k];
        for (let i = 0; i < n; i++) {
          const j = Math.min(Math.max(i + k - half, 0), n - 1); // edge-replicate padding
          out[i] += c * x[j];
        }
      }
      return out;
    }
    case "snv": {
      let mu = 0;
      for (const v of x) mu += v;
      mu /= x.length;
      let ss = 0;
      for (const v of x) ss += (v - mu) * (v - mu);
      const sd = Math.sqrt(ss / x.length);
      return x.map((v) => (v - mu) / sd);
    }
    case "msc": {
      const r = step.reference;
      const n = x.length;
      let rm = 0, xm = 0;
      for (let i = 0; i < n; i++) { rm += r[i]; xm += x[i]; }
      rm /= n; xm /= n;
      let num = 0, den = 0;
      for (let i = 0; i < n; i++) { num += (r[i] - rm) * (x[i] - xm); den += (r[i] - rm) * (r[i] - rm); }
      const b = num / den;
      const a = xm - b * rm;
      return x.map((v) => (v - a) / b);
    }
  }
}

export interface Prediction {
  prediction: number;
  half: number;
  interval: [number, number];
  leverage: number;
  q: number;
  scores: number[];
  stages: { name: string; x: Float64Array }[];
}

export function preprocess(model: PlsModel, spectrum: ArrayLike<number>) {
  let x: Float64Array = Float64Array.from(spectrum);
  const stages: { name: string; x: Float64Array }[] = [{ name: "raw", x }];
  for (const s of model.preprocessing) {
    x = applyStep(s, x);
    stages.push({ name: s.type, x });
  }
  return stages;
}

export function predict(model: PlsModel, spectrum: ArrayLike<number>): Prediction {
  const stages = preprocess(model, spectrum);
  const x = stages[stages.length - 1].x;
  const p = x.length;
  let y = model.b0;
  for (let j = 0; j < p; j++) y += x[j] * model.beta[j];
  const A = model.x_rotations.length;
  const xc = new Float64Array(p);
  for (let j = 0; j < p; j++) xc[j] = x[j] - model.x_mean[j];
  const t = new Array(A).fill(0);
  for (let a = 0; a < A; a++) {
    const r = model.x_rotations[a];
    let s = 0;
    for (let j = 0; j < p; j++) s += xc[j] * r[j];
    t[a] = s;
  }
  let h = 1 / model.n_train;
  for (let a = 0; a < A; a++) for (let b = 0; b < A; b++) h += t[a] * model.tt_inv[a][b] * t[b];
  let q = 0;
  for (let j = 0; j < p; j++) {
    let rec = 0;
    for (let a = 0; a < A; a++) rec += t[a] * model.x_loadings[a][j];
    const e = xc[j] - rec;
    q += e * e;
  }
  const half = model.t_quantile * model.rmsecv * Math.sqrt(1 + h);
  return { prediction: y, half, interval: [y - half, y + half], leverage: h, q, scores: t, stages };
}

export type Status = "PASS" | "REVIEW" | "FAIL";

/** Same rule as layer_a/conformity.py. */
export function conformity(model: PlsModel, pr: Prediction, lo: number, hi: number) {
  const [a, b] = pr.interval;
  const [rlo, rhi] = model.calibration_range;
  const reasons: string[] = [];
  if (pr.leverage > model.h_limit) reasons.push(`leverage ${pr.leverage.toFixed(3)} above limit ${model.h_limit.toFixed(3)} (unusual composition)`);
  if (pr.q > model.q_limit) reasons.push(`spectral residual above the 95th percentile of the calibration set (spectrum unlike training spectra)`);
  if (pr.prediction < rlo || pr.prediction > rhi) reasons.push(`prediction outside the calibration range ${rlo}–${rhi}`);
  const inSpace = reasons.length === 0;
  let status: Status = b < lo || a > hi ? "FAIL" : a >= lo && b <= hi ? "PASS" : "REVIEW";
  if (!inSpace && status === "PASS") status = "REVIEW";
  return { status, reasons, inSpace };
}
