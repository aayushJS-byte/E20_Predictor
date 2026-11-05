import * as d3 from "d3";
import type { Data, Sample } from "../lib/data";
import { crosshair, frame, linePath } from "../lib/chart";
import { predict } from "../lib/pls";
import { Mulberry32 } from "../lib/sim";
import { chapter, figure, fmt, h, legend } from "../lib/ui";
import { gradeLimits, sampleSelect, statusBlock } from "./layerA";

export function playground(d: Data) {
  const { sec, inner } = chapter("playground", 5, "Try to break it", "The real model on real held-out spectra, running in your browser. Damage the spectrum and watch the verdict.", "Playground");
  const { fig, body } = figure("Live prediction", ["REAL DATA"]);
  let sample: Sample = d.spectra.samples[0];
  const ctl = { noise: 0, tilt: 0, scale: 1, shift: 0, grade: "E10" as "E10" | "E20" };
  const sel = sampleSelect(d, (s) => { sample = s; run(); }, sample.id);
  const slider = (label: string, key: "noise" | "tilt" | "scale" | "shift", min: number, max: number, step: number, unit: string) => {
    const out = h("output", {}, `${ctl[key]}${unit}`);
    const inp = h("input", { type: "range", min, max, step, value: ctl[key], "aria-label": label }) as HTMLInputElement;
    inp.addEventListener("input", () => { ctl[key] = Number(inp.value); out.textContent = `${inp.value}${unit}`; run(); });
    return h("label", {}, h("span", {}, `${label} `, out), inp);
  };
  const grade = h("div", { class: "seg", role: "group", "aria-label": "Declared grade" });
  for (const g of ["E10", "E20"] as const) {
    const b = h("button", { "aria-pressed": String(g === ctl.grade) }, `declared ${g}`);
    b.addEventListener("click", () => { ctl.grade = g; grade.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); run(); });
    grade.append(b);
  }
  body.append(h("div", { class: "controls" },
    h("label", {}, "Test sample", sel),
    slider("Noise", "noise", 0, 1500, 50, ""),
    slider("Baseline tilt", "tilt", -6000, 6000, 250, ""),
    slider("Shift", "shift", -15, 15, 1, " cm⁻¹"),
    h("label", {}, "Declared grade", grade),
  ));
  const chartBox = h("div"), res = h("div", { class: "grid2", style: "margin-top:16px" });
  body.append(legend([{ label: "original", color: "var(--axis)" }, { label: "what the model sees", color: "var(--s1)" }]), chartBox, res);
  inner.append(h("p", { class: "note", style: "margin-bottom:20px" }, "Tip: declare E20. These are E0–E10 fuels, so the check should fail them."));

  function perturbed(): number[] {
    const x = sample.spectrum, n = x.length, wn = d.spectra.wavenumbers;
    const rng = new Mulberry32(12345);
    const out = new Array(n);
    for (let i = 0; i < n; i++) {
      const src = Math.min(n - 1, Math.max(0, i - ctl.shift));
      const j0 = Math.floor(src), fr = src - j0, j1 = Math.min(n - 1, j0 + 1);
      const v = x[j0] * (1 - fr) + x[j1] * fr;
      out[i] = v * ctl.scale + ctl.tilt * ((wn[i] - wn[0]) / (wn[n - 1] - wn[0])) + ctl.noise * rng.normal();
    }
    return out;
  }

  function run() {
    const xp = perturbed();
    const pe = predict(d.models.ethanol, xp), pw = predict(d.models.water, xp);
    chartBox.replaceChildren();
    const wn = d.spectra.wavenumbers;
    const f = frame(chartBox, { width: 1120, height: 280, margin: { top: 10, right: 16, bottom: 36, left: 52 }, x: d3.scaleLinear().domain([wn[0], wn[wn.length - 1]]), y: [Math.min(0, d3.min(xp)!), Math.max(d3.max(xp)!, d3.max(sample.spectrum)!) * 1.05], xLabel: "Raman shift, cm⁻¹", yLabel: "intensity" });
    f.g.append("path").attr("class", "line").attr("d", linePath(wn, sample.spectrum, f)).style("stroke", "var(--axis)").style("stroke-width", 1.5);
    f.g.append("path").attr("class", "line").attr("d", linePath(wn, xp, f)).style("stroke", "var(--s1)").style("stroke-width", 1.2);
    crosshair(f, () => [{ label: "original", color: "var(--axis)", xs: wn, ys: sample.spectrum, fmt: (v) => fmt(v, 0) }, { label: "model input", color: "var(--s1)", xs: wn, ys: xp, fmt: (v) => fmt(v, 0) }], (x) => `${fmt(x, 0)} cm⁻¹`);
    const [lo, hi] = gradeLimits(d, ctl.grade);
    res.replaceChildren(
      statusBlock(d.models.ethanol, pe, lo, hi, "% v/v", `Ethanol · declared ${ctl.grade}`, sample.ethanol_ref),
      statusBlock(d.models.water, pw, 0, d.resultsA.limits.water_max_mg_per_kg.value, "mg/kg", "Water · weak model", sample.water_ref),
    );
  }
  run();
  inner.append(fig);
  return sec;
}
