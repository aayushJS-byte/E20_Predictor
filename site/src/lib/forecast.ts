// Port of layer_b/physics_forecast.py (physics roll-forward from observables)
// plus the SAFE / WATCH / ACT rule. SYNTHETIC evaluation only.
import { type Constants, type Trace, type SimEvent, toleranceKg, pctVvToMgPerKg, segmentVolume } from "./sim";

export const HORIZON_H = 72;
const STEPS_PER_H = 2;
const WINDOW_DAYS = 7;
const RAIN_DAY_MM = 2.0;

const v = (c: Constants, ...path: string[]) => {
  let node: any = c;
  for (const p of path) node = node[p];
  return node && typeof node === "object" && "value" in node ? node.value : node;
};

const median = (a: number[]) => {
  const s = [...a].sort((x, y) => x - y);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : 0.5 * (s[m - 1] + s[m]);
};

export interface Obs {
  gauge_fuel_m3: ArrayLike<number>;
  gauge_lower_m3: Float64Array;
  sensor_water_mgkg: ArrayLike<number>;
  t_fuel: ArrayLike<number>;
  precip_mm: ArrayLike<number>;
  delivered_water_kg: Float64Array;
  drained_kg: Float64Array;
  diss: Float64Array;
  W: Float64Array;
}

export function observables(tr: Trace, events: SimEvent[], c: Constants, capacity: number): Obs {
  const n = tr.fuel_m3.length;
  const r = v(c, "tank", "tank_diameter_m") / 2;
  const len = capacity / (Math.PI * r * r);
  const rhoF = v(c, "physical", "density_e20"), rhoW = v(c, "physical", "density_water"), rhoE = v(c, "physical", "density_ethanol");
  const f = v(c, "lower_phase", "ethanol_mass_fraction");
  const rhoLow = 1 / (f / rhoE + (1 - f) / rhoW);
  const wSpec = pctVvToMgPerKg(c, v(c, "spec", "e20_max_water_content")) * 1e-6 * rhoF;
  const delivered = new Float64Array(n), drained = new Float64Array(n);
  for (const e of events) {
    if (e.type === "delivery") delivered[e.step] += wSpec * e.volume_m3;
    else if (e.type === "drain_out") drained[e.step] += e.water_kg;
  }
  const lower = new Float64Array(n), diss = new Float64Array(n), W = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    lower[i] = segmentVolume(tr.gauge_water_mm[i] / 1000, r, len);
    const fuelKg = tr.gauge_fuel_m3[i] * rhoF;
    diss[i] = tr.sensor_water_mgkg[i] * 1e-6 * fuelKg;
    const asWater = lower[i] * rhoW;
    const cap = toleranceKg(c, tr.gauge_t_fuel[i], fuelKg, 20);
    W[i] = diss[i] + (diss[i] + asWater > cap ? lower[i] * rhoLow * (1 - f) : asWater);
  }
  return {
    gauge_fuel_m3: tr.gauge_fuel_m3, gauge_lower_m3: lower, sensor_water_mgkg: tr.sensor_water_mgkg,
    t_fuel: tr.gauge_t_fuel, precip_mm: tr.precip_mm, delivered_water_kg: delivered, drained_kg: drained, diss, W,
  };
}

function robustRate(precip: number[], ingress: number[]) {
  const dryI = ingress.filter((_, k) => precip[k] < RAIN_DAY_MM);
  const base = dryI.length ? dryI : ingress;
  const mb = median(base);
  const a = Math.max(0, mb);
  const seA = (1.4826 * median(base.map((x) => Math.abs(x - mb)))) / Math.sqrt(base.length);
  let b = 0, seB = 0;
  const wet = precip.map((p, k) => [p, ingress[k]]).filter(([p]) => p >= RAIN_DAY_MM);
  if (wet.length >= 2) {
    const r = wet.map(([p, y]) => (y - a) / p);
    const bm = median(r);
    const se = (1.4826 * median(r.map((x) => Math.abs(x - bm)))) / Math.sqrt(wet.length);
    if (bm > 2 * se) { b = bm; seB = se; }
  }
  return { a, b, seA, seB };
}

export function fitIngress(o: Obs, i: number, c: Constants) {
  const sample = Math.trunc(v(c, "tank", "water_sample_interval_h")) * STEPS_PER_H;
  const all: number[] = [];
  for (let k = 0; k <= i; k += sample) all.push(k);
  const ks = all.slice(-(WINDOW_DAYS + 1));
  if (ks.length < 3) return { a: 0, b: 0, seA: 0, seB: 0 };
  const rhoF = v(c, "physical", "density_e20");
  const ys: number[] = [], xs: number[] = [];
  for (let q = 0; q + 1 < ks.length; q++) {
    const k0 = ks[q], k1 = ks[q + 1];
    let out = 0, known = 0, rain = 0;
    for (let k = k0 + 1; k <= k1; k++) {
      const dV = o.gauge_fuel_m3[k] - o.gauge_fuel_m3[k - 1];
      if (dV < 0) out -= dV;
      known += o.delivered_water_kg[k] - o.drained_kg[k];
      rain += o.precip_mm[k];
    }
    const dispensed = out * rhoF * o.sensor_water_mgkg[k0] * 1e-6;
    ys.push(o.W[k1] - o.W[k0] + dispensed - known);
    xs.push(rain);
  }
  const r = robustRate(xs, ys);
  return { a: r.a / sample, b: r.b, seA: r.seA / sample, seB: r.seB };
}

export interface Forecast {
  mid: number[];
  lo: number[];
  hi: number[];
  a: number;
  b: number;
  timeToSeparationH: number | null;
}

export function forecast(o: Obs, i: number, tFuelF: ArrayLike<number>, precipF: ArrayLike<number>, c: Constants): Forecast {
  const { a, b, seA, seB } = fitIngress(o, i, c);
  const d0 = o.diss[i];
  const b0 = o.W[i] - d0;
  const v0 = o.gauge_fuel_m3[i];
  const k0 = Math.max(0, i - 48);
  let rate = 0;
  if (i > 0) {
    let s = 0;
    for (let k = k0 + 1; k <= i; k++) s += Math.min(o.gauge_fuel_m3[k] - o.gauge_fuel_m3[k - 1], 0);
    rate = Math.max(0, -s / (i - k0));
  }
  const rhoF = v(c, "physical", "density_e20");
  const n = HORIZON_H * STEPS_PER_H;
  const cap = v(c, "tank", "capacity_m3");
  const trigger = v(c, "tank", "delivery_trigger_fraction") * cap;
  const dvol = v(c, "tank", "delivery_volume_m3");
  const wSpec = pctVvToMgPerKg(c, v(c, "spec", "e20_max_water_content")) * 1e-6 * rhoF;
  const V = new Float64Array(n), D = new Float64Array(n), C = new Float64Array(n);
  let vv = v0, d = d0;
  for (let k = 0; k < n; k++) {
    const outV = Math.min(rate, Math.max(vv - 1, 0));
    d -= vv > 0 ? (d * outV) / vv : 0;
    vv -= outV;
    if (vv < trigger) {
      const add = Math.min(dvol, 0.95 * cap - vv);
      vv += add;
      d += wSpec * add;
    }
    V[k] = vv; D[k] = d;
    C[k] = toleranceKg(c, tFuelF[k], vv * rhoF, 20);
  }
  const path = (aa: number, bb: number) => {
    const out: number[] = [];
    let B = b0;
    for (let k = 0; k < n; k++) {
      B += aa + bb * precipF[k];
      if ((k + 1) % STEPS_PER_H === 0) out.push(1 - (D[k] + B) / C[k]);
    }
    return out;
  };
  const mid = path(a, b);
  return {
    mid,
    lo: path(Math.max(0, a - 2 * seA), Math.max(0, b - 2 * seB)),
    hi: path(a + 2 * seA, b + 2 * seB),
    a, b,
    timeToSeparationH: timeToZero(mid),
  };
}

export function timeToZero(m: number[], hours?: number[]): number | null {
  const hs = hours ?? m.map((_, k) => k + 1);
  let prevH = 0, prevM: number | null = null;
  for (let k = 0; k < m.length; k++) {
    if (m[k] <= 0) {
      if (prevM === null || prevM <= 0) return prevM === null ? hs[k] : prevH;
      return prevH + ((hs[k] - prevH) * prevM) / (prevM - m[k]);
    }
    prevH = hs[k]; prevM = m[k];
  }
  return null;
}

export type AlertState = "SAFE" | "WATCH" | "ACT";

/** Same rule as layer_b/models.py; `margins[k]` is the forecast at hours[k]. */
export function alertState(margins: number[], hours: number[], c: Constants): AlertState {
  const actH = v(c, "alerts", "act_horizon_h"), watchH = v(c, "alerts", "watch_horizon_h");
  const actM = v(c, "alerts", "act_margin"), watchM = v(c, "alerts", "watch_margin");
  if (margins.some((m, k) => hours[k] <= actH && m <= actM)) return "ACT";
  if (margins.some((m, k) => hours[k] <= watchH && m < watchM)) return "WATCH";
  return "SAFE";
}
