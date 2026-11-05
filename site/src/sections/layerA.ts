import * as d3 from "d3";
import type { Data, Sample } from "../lib/data";
import { crosshair, frame, linePath } from "../lib/chart";
import { conformity, predict, preprocess, type PlsModel, type Prediction } from "../lib/pls";
import { callout, chapter, details, figure, fmt, h, scrolly, stat, table, tip } from "../lib/ui";

export function gradeLimits(d: Data, grade: "E10" | "E20") {
  return d.resultsA.limits[grade].ethanol as [number, number];
}

export function intervalBar(model: PlsModel, pr: Prediction, lo: number, hi: number, label: string) {
  const W = 420, H = 46, m = 6;
  const ext = [Math.min(lo, pr.interval[0], model.calibration_range[0]), Math.max(hi, pr.interval[1], model.calibration_range[1])];
  const pad = (ext[1] - ext[0]) * 0.06;
  const x = d3.scaleLinear().domain([ext[0] - pad, ext[1] + pad]).range([m, W - m]);
  const svg = d3.create("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", `${label}: prediction interval against limits`);
  svg.append("rect").attr("x", m).attr("width", W - 2 * m).attr("y", 12).attr("height", 10).attr("rx", 5).style("fill", "var(--surface)");
  svg.append("rect").attr("x", x(lo)).attr("width", Math.max(2, x(hi) - x(lo))).attr("y", 12).attr("height", 10).attr("rx", 5).style("fill", "var(--s3)").style("opacity", 0.35);
  svg.append("rect").attr("x", x(pr.interval[0])).attr("width", Math.max(2, x(pr.interval[1]) - x(pr.interval[0]))).attr("y", 14).attr("height", 6).attr("rx", 3).style("fill", "var(--ink)").style("opacity", 0.75);
  svg.append("circle").attr("cx", x(pr.prediction)).attr("cy", 17).attr("r", 6).style("fill", "var(--s1)").style("stroke", "var(--surface)").style("stroke-width", 2.5);
  svg.append("text").attr("x", x(lo)).attr("y", 40).attr("class", "axis-label").text(`${fmt(lo, 0)}`);
  svg.append("text").attr("x", x(hi)).attr("y", 40).attr("text-anchor", "end").attr("class", "axis-label").text(`limit ${fmt(hi, 0)}`);
  return svg.node() as SVGSVGElement;
}

export function statusBlock(model: PlsModel, pr: Prediction, lo: number, hi: number, unit: string, label: string, refVal: number | null) {
  const cf = conformity(model, pr, lo, hi);
  const dp = unit.startsWith("%") ? 2 : 0;
  return h("div", { class: "result-card" },
    h("div", { class: "top" }, h("span", { class: "label" }, label), h("span", { class: `status ${cf.status}` }, cf.status)),
    h("div", { class: "value" }, fmt(pr.prediction, dp), h("small", {}, `± ${fmt(pr.half, dp)} ${unit}`)),
    intervalBar(model, pr, lo, hi, label),
    h("div", { class: "sub" }, refVal === null ? "no lab value" : `lab value ${fmt(refVal, dp)} ${unit}`, cf.reasons.length ? ` · ${cf.reasons[0]}` : ""),
  );
}

export function sampleSelect(d: Data, onChange: (s: Sample) => void, initial: string) {
  const sel = h("select", { "aria-label": "Held-out test sample" }) as HTMLSelectElement;
  for (const s of d.spectra.samples) {
    const o = h("option", { value: s.id }, `${s.id} · ${s.ethanol_ref ?? "?"} % ethanol`);
    if (s.id === initial) o.setAttribute("selected", "");
    sel.append(o);
  }
  sel.addEventListener("change", () => onChange(d.spectra.samples.find((s) => s.id === sel.value)!));
  return sel;
}

export function layerA(d: Data) {
  const { sec, inner } = chapter("layer-a", 4, "Check every tanker", "A ten-second spectrum of each load, turned into ethanol and water content with an error bar, and a pass or fail.", "Layer A · depot");
  const rA = d.resultsA.targets;
  const mE = d.models.ethanol, mW = d.models.water;
  inner.append(callout("i", `<b>Raman, not NIR.</b> Our slides say NIR, but the public dataset with lab reference values is Raman: 179 real gasolines on a handheld 785 nm spectrometer. Both are calibrated with PLS.`));

  const initial = d.spectra.samples.reduce((a, b) => (Math.abs((b.ethanol_ref ?? 99) - 4.7) < Math.abs((a.ethanol_ref ?? 99) - 4.7) ? b : a)).id;
  let sample = d.spectra.samples.find((s) => s.id === initial)!;
  const wnIn = d.spectra.wavenumbers;

  const { fig, body } = figure("Held-out test sample", ["REAL DATA"]);
  const sel = sampleSelect(d, (s) => { sample = s; render(); }, initial);
  fig.querySelector(".fig-head > div")!.append(sel);
  sel.style.marginTop = "10px";
  const chartBox = h("div"), resultBox = h("div", { class: "grid2", style: "margin-top:16px" });
  body.append(chartBox, resultBox);

  let stepIdx = 0;
  function bands(f: any) {
    for (const b of d.resultsA.bands) {
      if (b.wavenumber < f.x.domain()[0] || b.wavenumber > f.x.domain()[1]) continue;
      f.g.append("line").attr("x1", f.x(b.wavenumber)).attr("x2", f.x(b.wavenumber)).attr("y1", 0).attr("y2", f.h).style("stroke", "var(--muted)").style("stroke-dasharray", "2 4");
      const first = b.wavenumber === 885;
      f.g.append("text").attr("class", "axis-label").attr("x", f.x(b.wavenumber) + (first ? -5 : 5)).attr("y", 10)
        .attr("text-anchor", first ? "end" : "start").text(first ? "ethanol 885" : "aromatics 1005");
    }
  }
  function render() {
    const stages = preprocess(mE, sample.spectrum);
    const pr = predict(mE, sample.spectrum);
    chartBox.replaceChildren();
    resultBox.replaceChildren();
    const crop = mE.preprocessing[0] as { start: number; stop: number };
    const wnC = wnIn.slice(crop.start, crop.stop);
    const opts = { height: 300, margin: { top: 10, right: 16, bottom: 36, left: 52 } };
    if (stepIdx <= 2) {
      const ys = stepIdx === 0 ? stages[0].x : stages[1].x;
      const xs = stepIdx === 0 ? wnIn : wnC;
      const f = frame(chartBox, { ...opts, x: d3.scaleLinear().domain([xs[0], xs[xs.length - 1]]), y: [0, (d3.max(ys) as number) * 1.05], xLabel: "Raman shift, cm⁻¹", yLabel: "intensity" });
      if (stepIdx === 0) f.g.append("rect").attr("x", f.x(wnC[0])).attr("width", f.x(wnC[wnC.length - 1]) - f.x(wnC[0])).attr("y", 0).attr("height", f.h).style("fill", "var(--s1-wash)");
      const area = d3.area<number>().x((_, i) => f.x(xs[i])).y0(f.h).y1((v) => f.y(v));
      f.g.append("path").attr("d", area(Array.from(ys)) ?? "").style("fill", "var(--s1-wash)");
      f.g.append("path").attr("class", "line").attr("d", linePath(xs, ys, f)).style("stroke", "var(--s1)").style("stroke-width", 1.5);
      const series = [{ label: "spectrum", color: "var(--s1)", xs, ys, fmt: (v: number) => fmt(v, 0) }];
      if (stepIdx === 2) {
        const base = stages[1].x.map((v, i) => v - stages[2].x[i]);
        f.g.append("path").attr("class", "line").attr("d", linePath(wnC, base, f)).style("stroke", "var(--s2)").style("stroke-width", 2.5);
        f.g.append("text").attr("class", "direct-label").attr("x", f.x(wnC[40])).attr("y", f.y(base[40]) - 10).text("fluorescence baseline");
        series.push({ label: "baseline", color: "var(--s2)", xs: wnC, ys: base, fmt: (v: number) => fmt(v, 0) });
      }
      bands(f);
      crosshair(f, () => series, (x) => `${fmt(x, 0)} cm⁻¹`);
    } else if (stepIdx === 3) {
      const y = stages[stages.length - 1].x;
      const f = frame(chartBox, { ...opts, x: d3.scaleLinear().domain([wnC[0], wnC[wnC.length - 1]]), y: [(d3.min(y) as number) - 0.3, (d3.max(y) as number) * 1.05], xLabel: "Raman shift, cm⁻¹", yLabel: "normalised" });
      f.g.append("path").attr("class", "line").attr("d", linePath(wnC, y, f)).style("stroke", "var(--s1)").style("stroke-width", 1.5);
      bands(f);
      crosshair(f, () => [{ label: "normalised", color: "var(--s1)", xs: wnC, ys: y }], (x) => `${fmt(x, 0)} cm⁻¹`);
    } else {
      const lv = rA.ethanol.lv_scores_dev;
      const ext = (a: number[], b: number) => [Math.min(d3.min(a) as number, b), Math.max(d3.max(a) as number, b)];
      const [x0, x1] = ext(lv.t1, pr.scores[0]);
      const [y0, y1] = ext(lv.t2, pr.scores[1]);
      const f = frame(chartBox, { ...opts, x: d3.scaleLinear().domain([x0 - 1, x1 + 1]), y: [y0 - 1, y1 + 1], xLabel: "latent variable 1", yLabel: "latent variable 2" });
      const col = d3.scaleSequential([0, 10], d3.interpolateRgb("#cde2fb", "#104281"));
      f.g.selectAll("circle.dev").data(d3.range(lv.t1.length)).join("circle").attr("class", "dev")
        .attr("cx", (i) => f.x(lv.t1[i])).attr("cy", (i) => f.y(lv.t2[i])).attr("r", 5)
        .style("fill", (i) => col(lv.y[i])).style("stroke", "var(--surface)").style("stroke-width", 1.5)
        .on("pointermove", (ev, i) => tip(`training sample<br><b>${fmt(lv.y[i], 1)} %</b> ethanol`, ev)).on("pointerleave", () => tip(null));
      f.g.append("circle").attr("cx", f.x(pr.scores[0])).attr("cy", f.y(pr.scores[1])).attr("r", 10).style("fill", "none").style("stroke", "var(--s2)").style("stroke-width", 3);
      f.g.append("text").attr("class", "direct-label").attr("x", f.x(pr.scores[0]) + 14).attr("y", f.y(pr.scores[1]) + 4).style("fill", "var(--ink)").text("this sample");
      f.g.append("text").attr("class", "axis-label").attr("x", f.w).attr("y", f.h - 8).attr("text-anchor", "end").text("dots: training samples, darker = more ethanol");
    }
    if (stepIdx >= 5) {
      const prW = predict(mW, sample.spectrum);
      const [lo, hi] = gradeLimits(d, "E10");
      resultBox.append(
        statusBlock(mE, pr, lo, hi, "% v/v", "Ethanol · declared E10", sample.ethanol_ref),
        statusBlock(mW, prW, 0, d.resultsA.limits.water_max_mg_per_kg.value, "mg/kg", "Water · weak model", sample.water_ref),
      );
    }
  }

  const { root, sticky } = scrolly(
    [
      ["1 · Raw spectrum", "Each peak is a molecular vibration. The broad hump underneath is fluorescence, not chemistry."],
      ["2 · Crop", "Keep 400–1800 cm⁻¹. Water's O–H band (~3400 cm⁻¹) is outside this instrument's range altogether."],
      ["3 · Remove baseline", "A smooth curve that hugs the bottom of the spectrum is fitted and subtracted (ALS)."],
      ["4 · Normalise", "Scale every spectrum to the same spread, so laser power and focus don't matter (SNV)."],
      ["5 · Project", "PLS compresses 1,401 numbers into 5 scores. A sample far from the cloud is flagged for review."],
      ["6 · Decide", "<b>PASS</b> if the whole error bar is inside the limit, <b>FAIL</b> if it is outside, <b>REVIEW</b> in between."],
    ],
    (i) => { stepIdx = i; render(); },
  );
  sticky.append(fig);
  inner.append(root);
  render();
  inner.append(resultsBlock(d));
  return sec;
}

function resultsBlock(d: Data) {
  const rA = d.resultsA.targets;
  const E = rA.ethanol.test.pls, Wt = rA.water.test;
  const wrap = h("div", { style: "margin-top:40px" });
  wrap.append(h("div", { class: "ch-head", style: "margin-bottom:28px" }, h("h2", { style: "font-size:2.2rem" }, "How well does it work?"), h("p", { class: "dek" }, `Scored once on ${rA.ethanol.n_test} samples the model never saw.`)));
  wrap.append(h("div", { class: "grid3" },
    stat(fmt(E.r2, 2), "R² for ethanol content", "REAL DATA"),
    stat(`±${fmt(E.rmsep, 2)}%`, "typical error (RMSEP), % v/v ethanol", "REAL DATA"),
    stat(fmt(E.rpd, 1), "RPD: above 3 is fit for screening", "REAL DATA"),
  ));

  const grid = h("div", { class: "grid2" });
  // parity
  const r = rA.ethanol;
  const p = figure("Predicted vs lab value · ethanol", ["REAL DATA"]);
  const ref: number[] = r.test_ref, pred: number[] = r.test_pred, half: number[] = r.test_pi_half;
  const lo = Math.min(0, d3.min(pred.map((v, i) => v - half[i]))!), hi = Math.max(d3.max(ref)!, d3.max(pred.map((v, i) => v + half[i]))!);
  const f = frame(p.body, { width: 480, height: 380, margin: { top: 10, right: 16, bottom: 40, left: 44 }, x: d3.scaleLinear().domain([lo, hi]), y: [lo, hi], xLabel: "lab, % v/v", yLabel: "predicted, % v/v" });
  f.g.append("line").attr("x1", f.x(lo)).attr("x2", f.x(hi)).attr("y1", f.y(lo)).attr("y2", f.y(hi)).style("stroke", "var(--axis)").style("stroke-dasharray", "4 4");
  f.g.selectAll("line.pi").data(d3.range(ref.length)).join("line").attr("x1", (i) => f.x(ref[i])).attr("x2", (i) => f.x(ref[i]))
    .attr("y1", (i) => f.y(pred[i] - half[i])).attr("y2", (i) => f.y(pred[i] + half[i])).style("stroke", "var(--s1)").style("opacity", 0.22).style("stroke-width", 2);
  f.g.selectAll("circle.pt").data(d3.range(ref.length)).join("circle").attr("cx", (i) => f.x(ref[i])).attr("cy", (i) => f.y(pred[i])).attr("r", 5)
    .style("fill", "var(--s1)").style("stroke", "var(--surface)").style("stroke-width", 2)
    .on("pointermove", (ev, i) => tip(`${r.test_ids[i]}<br><span class="k">lab</span> <b>${fmt(ref[i], 2)}</b> · <span class="k">model</span> <b>${fmt(pred[i], 2)}</b>`, ev))
    .on("pointerleave", () => tip(null));
  grid.append(p.fig);
  // VIP
  const v = figure("What the model looks at", ["REAL DATA"], "importance by wavenumber");
  const wn: number[] = r.wavenumbers_model, vip: number[] = r.vip;
  const fv = frame(v.body, { width: 480, height: 380, margin: { top: 10, right: 16, bottom: 40, left: 36 }, x: d3.scaleLinear().domain([wn[0], wn[wn.length - 1]]), y: [0, d3.max(vip)! * 1.12], xLabel: "Raman shift, cm⁻¹", yLabel: "VIP" });
  fv.g.append("path").attr("d", d3.area<number>().x((_, i) => fv.x(wn[i])).y0(fv.h).y1((y) => fv.y(y))(vip) ?? "").style("fill", "var(--s1-wash)");
  fv.g.append("path").attr("class", "line").attr("d", linePath(wn, vip, fv)).style("stroke", "var(--s1)").style("stroke-width", 1.5);
  const b885 = d.resultsA.bands[0];
  const vAt = vip[wn.findIndex((w) => w >= b885.wavenumber)];
  fv.g.append("circle").attr("cx", fv.x(b885.wavenumber)).attr("cy", fv.y(vAt)).attr("r", 5).style("fill", "var(--s2)").style("stroke", "var(--surface)").style("stroke-width", 2);
  fv.g.append("text").attr("class", "direct-label").attr("x", fv.x(b885.wavenumber) + 10).attr("y", fv.y(vAt) - 6).text("ethanol C–C–O, 885");
  crosshair(fv, () => [{ label: "VIP", color: "var(--s1)", xs: wn, ys: vip, fmt: (x) => fmt(x, 2) }], (x) => `${fmt(x, 0)} cm⁻¹`);
  grid.append(v.fig);
  wrap.append(grid);

  wrap.append(callout("×", `<b>Water doesn't work, and that's expected.</b> R² ${fmt(Wt.pls.r2, 2)}, no better than guessing water from ethanol alone (${fmt(Wt.ethanol_proxy_reference.r2, 2)}). The O–H band is out of range. Use NIR or Karl Fischer for water.`));
  wrap.append(callout("!", `<b>Recalibrate before use.</b> The samples are European E0–E10 petrol, and here ethanol tracks the ether ETBE (r = −0.76). Indian E20 has neither feature.`));

  // full metrics
  const m = (t: string, k: string) => rA[t].test[k];
  const row = (name: string, t: string, k: string, d0: number) => {
    const x = m(t, k);
    return [name, fmt(x.r2, 3), fmt(x.rmsep, d0), fmt(x.sep, d0), fmt(x.bias, d0), fmt(x.rpd, 2), x.n_lv ?? "–"];
  };
  const tbl = table(["model", "R²", "RMSEP", "SEP", "bias", "RPD", "LVs"], [
    row("Ethanol · PLS", "ethanol", "pls", 2), row("Ethanol · ridge", "ethanol", "ridge", 2), row("Ethanol · predict the mean", "ethanol", "predict_dev_mean", 2),
    row("Water · PLS (mg/kg)", "water", "pls", 0), row("Water · ridge", "water", "ridge", 0), row("Water · from lab ethanol only", "water", "ethanol_proxy_reference", 0),
  ], { numeric: [1, 2, 3, 4, 5, 6] });
  const cvBox = h("div");
  const curve: number[] = r.selection.cv_curve, se: number[] = r.selection.cv_curve_se, ks = curve.map((_, i) => i + 1);
  const fc = frame(cvBox, { width: 700, height: 220, margin: { top: 10, right: 16, bottom: 36, left: 44 }, x: d3.scaleLinear().domain([0.5, ks.length + 0.5]), y: [0, d3.max(curve.map((v2, i) => v2 + se[i]))! * 1.08], xLabel: "latent variables", yLabel: "CV error, % v/v" });
  fc.g.append("path").attr("class", "line").attr("d", linePath(ks, curve, fc)).style("stroke", "var(--s1)");
  fc.g.append("circle").attr("cx", fc.x(r.selection.n_lv)).attr("cy", fc.y(curve[r.selection.n_lv - 1])).attr("r", 6).style("fill", "var(--s2)").style("stroke", "var(--surface)").style("stroke-width", 2);
  fc.g.append("text").attr("class", "direct-label").attr("x", fc.x(r.selection.n_lv) + 10).attr("y", fc.y(curve[r.selection.n_lv - 1]) - 8).text(`chosen: ${r.selection.n_lv}`);
  wrap.append(details("All metrics and model selection", h("div", {}, tbl,
    h("p", { class: "note" }, `Pipeline, window and number of latent variables chosen by 10-fold cross-validation on the ${rA.ethanol.n_dev} train + validation samples (one-SE rule). Test set scored once.`), cvBox), "REAL DATA"));
  return wrap;
}
