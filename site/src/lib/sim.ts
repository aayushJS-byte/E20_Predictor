// Line-for-line port of sim/tank.py (the E20 underground tank simulator).
// SYNTHETIC (physics-informed). Equivalence with Python is tested in tests/sim.test.ts.

export interface Constants {
  [k: string]: any;
}

export interface TankParams {
  capacity_m3: number;
  initial_fill_fraction: number;
  delivery_trigger_fraction: number;
  delivery_volume_m3: number;
  dispense_m3_per_day: number;
  ullage_ambient_coupling: number;
  moisture_capture_efficiency: number;
  seal: "none" | "minor" | "major";
  seal_fault_start_day: number;
  wet_tanker_probability: number;
  wet_tanker_water_L: number;
  dissolution_kg_per_day: number;
  drain_out: boolean;
  drain_interval_days: number;
  drain_fraction: number;
  ethanol_pct: number;
  rh_offset: number;
  swing_scale: number;
  seed: number;
  // validation-only stress knobs (optional; default = configured values)
  tolerance_scale?: number;
  catchment_scale?: number;
  sensor_sigma_scale?: number;
  lower_phase_ethanol_fraction?: number | null;
}

export interface Weather {
  times: string[]; // "YYYY-MM-DDTHH:MM"
  t_amb: number[];
  rh: number[];
  precip_mm: number[];
  t_soil: number[];
}

export const STEPS_PER_DAY = 48;

const v = (c: Constants, ...path: string[]) => {
  let node: any = c;
  for (const p of path) node = node[p];
  return node && typeof node === "object" && "value" in node ? node.value : node;
};

export function defaultParams(c: Constants): TankParams {
  const t = (k: string) => v(c, "tank", k);
  return {
    capacity_m3: t("capacity_m3"),
    initial_fill_fraction: t("initial_fill_fraction"),
    delivery_trigger_fraction: t("delivery_trigger_fraction"),
    delivery_volume_m3: t("delivery_volume_m3"),
    dispense_m3_per_day: t("dispense_m3_per_day"),
    ullage_ambient_coupling: t("ullage_ambient_coupling"),
    moisture_capture_efficiency: t("moisture_capture_efficiency"),
    seal: "none",
    seal_fault_start_day: 0,
    wet_tanker_probability: t("wet_tanker_probability"),
    wet_tanker_water_L: t("wet_tanker_water_L"),
    dissolution_kg_per_day: t("bottom_water_dissolution_kg_per_day"),
    drain_out: false,
    drain_interval_days: t("drain_out_interval_days"),
    drain_fraction: t("drain_out_removes_free_phase_fraction"),
    ethanol_pct: 20,
    rh_offset: 0,
    swing_scale: 1,
    seed: 0,
  };
}

// ---------------------------------------------------------------- PRNG
export class Mulberry32 {
  private a: number;
  constructor(seed: number) {
    this.a = seed >>> 0;
  }
  random(): number {
    this.a = (this.a + 0x6d2b79f5) >>> 0;
    let t = this.a;
    t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
    t = (t ^ ((t + (Math.imul(t ^ (t >>> 7), t | 61) >>> 0)) >>> 0)) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  normal(): number {
    const u1 = Math.max(this.random(), 1e-12);
    const u2 = this.random();
    return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  }
}

// ---------------------------------------------------------------- physics
export function waterToleranceWtPct(c: Constants, tempC: number, ethanolPct = 20): number {
  const corr = c.water_tolerance.correlation;
  const poly = (k: number[], e: number) => k[0] * e * e + k[1] * e + k[2];
  const a = poly(corr.a, ethanolPct), b = poly(corr.b, ethanolPct), cc = poly(corr.c, ethanolPct);
  return a * tempC * tempC + b * tempC + cc;
}

export function toleranceKg(c: Constants, tempC: number, fuelKg: number, ethanolPct = 20): number {
  const w = waterToleranceWtPct(c, tempC, ethanolPct) / 100;
  return (fuelKg * w) / (1 - w);
}

export function pctVvToMgPerKg(c: Constants, pctVv: number): number {
  return (pctVv / 100) * v(c, "physical", "density_water") / v(c, "physical", "density_e20") * 1e6;
}

function psat(t: number, m: { A_hPa: number; B: number; C_degC: number }) {
  return 100 * m.A_hPa * Math.exp((m.B * t) / (m.C_degC + t));
}

export function segmentVolume(h: number, r: number, len: number): number {
  if (h <= 0) return 0;
  h = Math.min(h, 2 * r);
  return len * (r * r * Math.acos((r - h) / r) - (r - h) * Math.sqrt(2 * r * h - h * h));
}

export function segmentHeight(vol: number, r: number, len: number): number {
  if (vol <= 0) return 0;
  let lo = 0, hi = 2 * r;
  for (let i = 0; i < 40; i++) {
    const mid = 0.5 * (lo + hi);
    if (segmentVolume(mid, r, len) < vol) lo = mid;
    else hi = mid;
  }
  return 0.5 * (lo + hi);
}

export function ambientWithSliders(w: Weather, p: TankParams) {
  const n = w.t_amb.length;
  const half = STEPS_PER_DAY / 2;
  const cs = new Float64Array(n + 1);
  for (let i = 0; i < n; i++) cs[i + 1] = cs[i] + w.t_amb[i];
  const tAmb = new Float64Array(n);
  const rh = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const lo = Math.max(i - half, 0), hi = Math.min(i + half, n);
    const mean24 = (cs[hi] - cs[lo]) / (hi - lo);
    tAmb[i] = mean24 + p.swing_scale * (w.t_amb[i] - mean24);
    rh[i] = Math.min(Math.max(w.rh[i] + p.rh_offset, 0), 100);
  }
  return { tAmb, rh };
}

export type SimEvent = { step: number; type: string; [k: string]: any };

export const TRACE_KEYS = [
  "fuel_m3", "ullage_m3", "t_fuel", "t_ullage", "t_amb", "rh", "precip_mm", "dissolved_kg", "bottom_kg",
  "lower_water_kg", "lower_phase_m3", "tolerance_kg", "margin", "water_mgkg", "ethanol_pct", "air_in_m3",
  "ingress_vapour_kg", "ingress_liquid_kg", "gauge_fuel_m3", "gauge_water_mm", "gauge_t_fuel", "book_m3",
  "recon_L", "sensor_water_mgkg",
] as const;
export type Trace = Record<(typeof TRACE_KEYS)[number], Float64Array>;

export function simulate(w: Weather, p: TankParams, c: Constants) {
  const K = {
    R: v(c, "physical", "gas_constant"),
    Mw: v(c, "physical", "molar_mass_water"),
    P: v(c, "physical", "atmospheric_pressure"),
    rho_w: v(c, "physical", "density_water"),
    rho_f: v(c, "physical", "density_e20"),
    rho_e: v(c, "physical", "density_ethanol"),
    magnus: v(c, "physical", "magnus"),
    f_low: v(c, "lower_phase", "ethanol_mass_fraction"),
    catch: v(c, "tank", "seal_fault_catchment_m2"),
    diam: v(c, "tank", "tank_diameter_m"),
    noise_h_mm: v(c, "tank", "gauge_noise_water_level_mm"),
    noise_v_L: v(c, "tank", "gauge_noise_fuel_volume_L"),
    sensor_sigma: v(c, "tank", "water_sensor_sigma_mg_per_kg"),
    sample_h: v(c, "tank", "water_sample_interval_h"),
    w_delivered_mgkg: pctVvToMgPerKg(c, v(c, "spec", "e20_max_water_content")),
  };
  if (p.lower_phase_ethanol_fraction != null) K.f_low = p.lower_phase_ethanol_fraction;
  K.sensor_sigma *= p.sensor_sigma_scale ?? 1;
  const tolScale = p.tolerance_scale ?? 1;
  const evRng = new Mulberry32(p.seed * 2 + 1);
  const noiseRng = new Mulberry32(p.seed * 2 + 2);
  const { tAmb, rh: rhArr } = ambientWithSliders(w, p);
  const n = w.t_amb.length;
  const hours = w.times.map((s) => Number(s.slice(11, 13)) + Number(s.slice(14, 16)) / 60);

  const radius = K.diam / 2;
  const length = p.capacity_m3 / (Math.PI * radius * radius);
  const catchment: number = K.catch[p.seal] * (p.catchment_scale ?? 1);
  const sealStart = Math.trunc(p.seal_fault_start_day * STEPS_PER_DAY);
  const dispRate = p.dispense_m3_per_day / 16 / 2;

  let V = p.initial_fill_fraction * p.capacity_m3;
  let V_eth = (V * p.ethanol_pct) / 100;
  let D = K.w_delivered_mgkg * 1e-6 * V * K.rho_f;
  let B = 0, S = 0, E_low = 0;
  let book = V;
  const ledger: Record<string, number> = {
    in_breathing: 0, in_rain: 0, in_wet_tanker: 0, in_delivery_dissolved: 0,
    out_dispensed: 0, out_drained: 0, stored_start: D + B + S,
  };
  const events: SimEvent[] = [];
  let lastDelivery = -1e9;
  let lastDrainDay = -1;
  let separated = false;
  const rhoLow = 1 / (K.f_low / K.rho_e + (1 - K.f_low) / K.rho_w);
  const tr = Object.fromEntries(TRACE_KEYS.map((k) => [k, new Float64Array(n)])) as Trace;

  let T_ull_prev = w.t_soil[0] + p.ullage_ambient_coupling * (tAmb[0] - w.t_soil[0]);
  let U_prev = p.capacity_m3 - V;
  let nextSample = 0;

  for (let i = 0; i < n; i++) {
    const ta = tAmb[i], rh = rhArr[i], tSoil = w.t_soil[i], precip = w.precip_mm[i], hr = hours[i];
    const T_fuel = tSoil;
    const T_ull = tSoil + p.ullage_ambient_coupling * (ta - tSoil);
    const day = Math.floor(i / STEPS_PER_DAY);

    if (V < p.delivery_trigger_fraction * p.capacity_m3 && hr >= 8 && hr < 18 && i - lastDelivery >= 12) {
      const vol = Math.min(p.delivery_volume_m3, 0.95 * p.capacity_m3 - V);
      const wIn = K.w_delivered_mgkg * 1e-6 * vol * K.rho_f;
      V += vol;
      V_eth += (vol * p.ethanol_pct) / 100;
      D += wIn;
      book += vol;
      ledger.in_delivery_dissolved += wIn;
      const wet = evRng.random() < p.wet_tanker_probability;
      const ev: SimEvent = { step: i, type: "delivery", volume_m3: vol, wet };
      if (wet) {
        const wkg = (p.wet_tanker_water_L * K.rho_w) / 1000;
        B += wkg;
        ledger.in_wet_tanker += wkg;
        ev.free_water_kg = wkg;
      }
      events.push(ev);
      lastDelivery = i;
    }

    if (hr >= 6 && hr < 22 && V > 0.05 * p.capacity_m3) {
      const withdrawn = Math.min(dispRate, V - 0.05 * p.capacity_m3);
      const frac = withdrawn / V;
      ledger.out_dispensed += D * frac;
      D -= D * frac;
      V_eth -= V_eth * frac;
      V -= withdrawn;
      book -= withdrawn;
    }

    let U = p.capacity_m3 - V - (S + E_low) / rhoLow;
    const gasNow = (U_prev * (T_ull + 273.15)) / (T_ull_prev + 273.15);
    const airIn = Math.max(0, U - gasNow);
    const nIn = (K.P * airIn) / (K.R * (T_ull + 273.15));
    const pv = (psat(ta, K.magnus) * rh) / 100;
    const wVap = p.moisture_capture_efficiency * nIn * (pv / K.P) * K.Mw;
    D += wVap;
    ledger.in_breathing += wVap;

    let wRain = 0;
    if (catchment > 0 && i >= sealStart && precip > 0) {
      wRain = (precip / 1000) * catchment * K.rho_w;
      B += wRain;
      ledger.in_rain += wRain;
    }

    const fuelMass = V * K.rho_f;
    const ethPct = (100 * V_eth) / V;
    const C = toleranceKg(c, T_fuel, fuelMass, ethPct) * tolScale;
    if (B > 0 && D < C && S === 0) {
      const j = Math.min(B, (p.dissolution_kg_per_day / STEPS_PER_DAY) * (1 - D / C));
      B -= j;
      D += j;
    }
    if (D + B > C || (S > 0 && B > 0)) {
      // settled water becomes the lower phase, plus any dissolved water above C; once a lower phase exists, new settled water joins it
      const excess = B + Math.max(0, D - C);
      D = Math.min(D, C);
      B = 0;
      S += excess;
      let eDrag = (excess * K.f_low) / (1 - K.f_low);
      eDrag = Math.min(eDrag, 0.9 * V_eth * K.rho_e);
      E_low += eDrag;
      V_eth -= eDrag / K.rho_e;
      V -= eDrag / K.rho_e;
      if (!separated) {
        events.push({ step: i, type: "separation_onset", excess_kg: excess });
        separated = true;
      }
    }

    if (p.drain_out && day % Math.trunc(p.drain_interval_days) === 0 && day !== lastDrainDay && hr === 7) {
      const removedW = p.drain_fraction * (B + S);
      const removedE = p.drain_fraction * E_low;
      ledger.out_drained += removedW;
      events.push({ step: i, type: "drain_out", water_kg: removedW, ethanol_kg: removedE, was_separated: S > 0 });
      B -= p.drain_fraction * B;
      S -= p.drain_fraction * S;
      E_low -= removedE;
      if (S <= 1e-9) {
        S = 0;
        E_low = 0;
        separated = false;
      }
      lastDrainDay = day;
    }

    if (catchment > 0 && i === sealStart) events.push({ step: i, type: "seal_fault_start", seal: p.seal });

    const lowVol = (S + E_low) / rhoLow + B / K.rho_w;
    const hW = segmentHeight(lowVol, radius, length) * 1000;
    const gaugeFuel = V + (noiseRng.normal() * K.noise_v_L) / 1000;
    const gaugeH = Math.max(0, hW + noiseRng.normal() * K.noise_h_mm);
    let sensor: number;
    if (i >= nextSample) {
      sensor = (D / fuelMass) * 1e6 + noiseRng.normal() * K.sensor_sigma;
      nextSample = i + K.sample_h * 2;
    } else {
      sensor = i > 0 ? tr.sensor_water_mgkg[i - 1] : NaN;
    }

    const C_now = toleranceKg(c, T_fuel, V * K.rho_f, (100 * V_eth) / V) * tolScale;
    U = p.capacity_m3 - V - lowVol;
    tr.fuel_m3[i] = V;
    tr.ullage_m3[i] = U;
    tr.t_fuel[i] = T_fuel;
    tr.t_ullage[i] = T_ull;
    tr.t_amb[i] = ta;
    tr.rh[i] = rh;
    tr.precip_mm[i] = precip;
    tr.dissolved_kg[i] = D;
    tr.bottom_kg[i] = B;
    tr.lower_water_kg[i] = S;
    tr.lower_phase_m3[i] = (S + E_low) / rhoLow;
    tr.tolerance_kg[i] = C_now;
    // <= 0 exactly while a lower phase exists (it is not re-mixed by dilution)
    tr.margin[i] = S === 0 ? 1 - (D + B + S) / C_now : Math.min(0, 1 - (D + B + S) / C_now);
    tr.water_mgkg[i] = (D / (V * K.rho_f)) * 1e6;
    tr.ethanol_pct[i] = (100 * V_eth) / V;
    tr.air_in_m3[i] = airIn;
    tr.ingress_vapour_kg[i] = wVap;
    tr.ingress_liquid_kg[i] = wRain;
    tr.gauge_fuel_m3[i] = gaugeFuel;
    tr.gauge_water_mm[i] = gaugeH;
    tr.gauge_t_fuel[i] = T_fuel;
    tr.book_m3[i] = book;
    tr.recon_L[i] = (gaugeFuel - book) * 1000;
    tr.sensor_water_mgkg[i] = sensor;
    U_prev = U;
    T_ull_prev = T_ull;
  }
  ledger.stored_end = D + B + S;
  ledger.water_in = ledger.in_breathing + ledger.in_rain + ledger.in_wet_tanker + ledger.in_delivery_dissolved;
  ledger.water_out = ledger.out_dispensed + ledger.out_drained;
  ledger.imbalance = ledger.water_in - ledger.water_out - (ledger.stored_end - ledger.stored_start);
  return { trace: tr, events, ledger };
}
