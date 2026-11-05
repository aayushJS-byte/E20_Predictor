import * as d3 from "d3";
import type { Data } from "../lib/data";
import { crosshair, frame, linePath } from "../lib/chart";
import { alertState, forecast, observables } from "../lib/forecast";
import { simulate, type TankParams, type Weather } from "../lib/sim";
import { chapter, figure, fmt, h, legend } from "../lib/ui";

export function twin(d: Data) {
  const { sec, inner } = chapter("twin", 6, "Watch every tank", "A simulated tank under real monsoon weather. Change the conditions; the simulator and forecast rerun live.", "Layer B · retail");
  const tw = d.twin;
  const c = d.constants;
  const weather: Weather = { times: tw.times, ...tw.weather };
  const times: number[] = tw.times.map((s: string) => new Date(s).getTime());
  const [w0, w1] = tw.window_steps as [number, number];
  const defaults: TankParams = { ...tw.params };

  const state = { p: { ...defaults }, cursor: w0 + 48 * 4, playing: false, isDefault: true };
  let run = simulate(weather, state.p, c);
  let obs = observables(run.trace, run.events, c, state.p.capacity_m3);

  const { fig, body, caption } = figure("Margin to separation · 26 Jun – 9 Jul 2024", ["SYNTHETIC (physics-informed)", "REAL DATA (ERA5 reanalysis)"], "margin = 1 − water in tank ÷ water the fuel can hold");

  // ---- controls
  const mkSlider = (label: string, min: number, max: number, step: number, get: () => number, set: (v: number) => void, show: (v: number) => string) => {
    const out = h("output", {}, show(get()));
    const inp = h("input", { type: "range", min, max, step, value: get(), "aria-label": label }) as HTMLInputElement;
    inp.addEventListener("input", () => { set(Number(inp.value)); out.textContent = show(Number(inp.value)); resim(); });
    return { el: h("label", {}, h("span", {}, `${label} `, out), inp), inp, out };
  };
  const sRh = mkSlider("Humidity", -30, 30, 5, () => state.p.rh_offset, (v) => (state.p.rh_offset = v), (v) => `${v >= 0 ? "+" : ""}${v} pts`);
  const sSw = mkSlider("Day–night swing", 0.5, 2.5, 0.25, () => state.p.swing_scale, (v) => (state.p.swing_scale = v), (v) => `×${v}`);
  const sUl = mkSlider("Refill at", 0.1, 0.6, 0.05, () => state.p.delivery_trigger_fraction, (v) => (state.p.delivery_trigger_fraction = v), (v) => `${Math.round(v * 100)} % full`);
  const seal = h("div", { class: "seg", role: "group", "aria-label": "Seal condition" });
  for (const s of ["none", "minor", "major"] as const) {
    const b = h("button", { "aria-pressed": String(s === state.p.seal) }, s === "none" ? "sealed" : `${s} leak`);
    b.addEventListener("click", () => { state.p.seal = s; seal.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); resim(); });
    seal.append(b);
  }
  const drain = h("input", { type: "checkbox", "aria-label": "Weekly drain-out (Solution 4)" }) as HTMLInputElement;
  drain.addEventListener("change", () => { state.p.drain_out = drain.checked; resim(); });
  const reset = h("button", {}, "Reset");
  reset.addEventListener("click", () => {
    state.p = { ...defaults };
    sRh.inp.value = "0"; sRh.out.textContent = "+0 pts"; sSw.inp.value = "1"; sSw.out.textContent = "×1";
    sUl.inp.value = String(defaults.delivery_trigger_fraction); sUl.out.textContent = `${Math.round(defaults.delivery_trigger_fraction * 100)} % full`;
    drain.checked = false;
    seal.querySelectorAll("button").forEach((x, k) => x.setAttribute("aria-pressed", String(k === 2)));
    resim();
  });
  const play = h("button", { class: "primary" }, "Play");
  const scrub = h("input", { type: "range", min: w0, max: w1, step: 1, value: state.cursor, "aria-label": "Replay time" }) as HTMLInputElement;
  scrub.style.width = "100%";
  scrub.addEventListener("input", () => { state.cursor = Number(scrub.value); draw(); });
  play.addEventListener("click", () => { state.playing = !state.playing; play.textContent = state.playing ? "Pause" : "Play"; if (state.playing) loop(); });

  body.append(
    h("div", { class: "controls" }, sRh.el, sSw.el, sUl.el, h("label", {}, "Fill-cap seal", seal),
      h("label", { class: "toggle" }, drain, "Weekly drain-out"), reset),
    h("div", { class: "controls", style: "align-items:center;flex-wrap:nowrap" }, play, scrub),
  );
  const tiles = h("div", { class: "readouts" });
  const legendBox = h("div");
  const chartA = h("div"), chartB = h("div"), chartC = h("div");
  body.append(tiles, legendBox, chartA, chartB, chartC);

  const xDom = d3.scaleTime().domain([times[w0], times[w1] + 72 * 3600e3]);
  const tf = (t: number) => d3.timeFormat("%d %b %H:%M")(new Date(t));

  function resim() {
    state.isDefault = JSON.stringify(state.p) === JSON.stringify(defaults);
    run = simulate(weather, state.p, c);
    obs = observables(run.trace, run.events, c, state.p.capacity_m3);
    draw();
  }

  function draw() {
    const i = state.cursor;
    const T = run.trace;
    const n = 144;
    const fc = forecast(obs, i, T.gauge_t_fuel.subarray(i + 1, i + 1 + n), T.precip_mm.subarray(i + 1, i + 1 + n), c);
    const hours = fc.mid.map((_, k) => k + 1);
    const alert = alertState(fc.mid, hours, c); // same rule and forecast as evaluated in layer_b/models.py
    const onset = run.events.find((e) => e.type === "separation_onset");
    const rainKg = d3.sum(T.ingress_liquid_kg.subarray(0, i + 1));
    const separatedNow = T.margin[i] <= 0;
    const tile = (l: string, v: string | Node, s: string, hero = false) => h("div", { class: "tile" }, h("div", { class: "label" }, l), h("div", { class: `value ${hero ? "big" : ""}` }, v), h("div", { class: "sub" }, s));
    tiles.replaceChildren(
      tile("Forecast time to separation", separatedNow ? "now" : fc.timeToSeparationH === null ? "> 72 h" : `${fmt(fc.timeToSeparationH, 0)} h`, `from ${tf(times[i])}`, true),
      tile("Alert", h("span", { class: `status ${separatedNow ? "ACT" : alert}` }, separatedNow ? "ACT" : alert), "ACT ≤ 0 in 48 h · WATCH < 25 % in 72 h"),
      tile("First separation", onset ? tf(times[onset.step]) : "none by 15 Aug", `${fmt(rainKg, 0)} kg of rain in so far`),
    );

    // ---- A: margin + cone
    chartA.replaceChildren();
    const fa = frame(chartA, { width: 1120, height: 300, margin: { top: 6, right: 16, bottom: 30, left: 48 }, x: xDom.copy(), y: [-0.4, 1], yLabel: "margin", xFormat: (t: Date) => d3.timeFormat("%d %b")(t), yFormat: (v) => `${Math.round(v * 100)} %` });
    fa.g.append("rect").attr("x", 0).attr("width", fa.w).attr("y", fa.y(0)).attr("height", fa.h - fa.y(0)).style("fill", "var(--s2-wash)");
    fa.g.append("text").attr("class", "direct-label").attr("x", 6).attr("y", fa.y(0) + 16).text("separated");
    fa.g.append("line").attr("x1", 0).attr("x2", fa.w).attr("y1", fa.y(0.25)).attr("y2", fa.y(0.25)).style("stroke", "var(--axis)").style("stroke-dasharray", "4 3");
    fa.g.append("text").attr("class", "axis-label").attr("x", 6).attr("y", fa.y(0.25) - 4).text("WATCH threshold");
    const hx = d3.range(w0, i + 1);
    const hxT = hx.map((k) => times[k]);
    const hm = hx.map((k) => Math.max(-0.4, T.margin[k]));
    fa.g.append("path").attr("class", "line").attr("d", linePath(hxT, hm, fa)).style("stroke", "var(--s1)");
    const fT = hours.map((hh) => times[i] + hh * 3600e3);
    const cone = d3.area<number>().x((_, k) => fa.x(fT[k])).y0((_, k) => fa.y(Math.max(-0.4, fc.lo[k]))).y1((_, k) => fa.y(Math.max(-0.4, fc.hi[k])));
    fa.g.append("path").attr("d", cone(hours) ?? "").style("fill", "var(--s2-wash)").style("stroke", "none");
    fa.g.append("path").attr("class", "line").attr("d", linePath(fT, fc.mid.map((v) => Math.max(-0.4, v)), fa)).style("stroke", "var(--s2)").style("stroke-dasharray", "5 3");
    const series: any[] = [
      { label: "margin (simulated)", color: "var(--s1)", xs: hxT, ys: hm, fmt: (v: number) => `${fmt(v * 100, 0)} %` },
      { label: "physics forecast", color: "var(--s2)", xs: fT, ys: fc.mid, fmt: (v: number) => `${fmt(v * 100, 0)} %` },
    ];
    let gbmNote = "";
    if (state.isDefault) {
      const fcs: any[] = tw.forecasts;
      const g = fcs.filter((x) => x.step <= i).pop();
      if (g) {
        const gx = (tw.horizons_h as number[]).map((hh) => times[g.step] + hh * 3600e3);
        fa.g.append("path").attr("class", "line").attr("d", linePath(gx, g.gbm.map((v: number) => Math.max(-0.4, v)), fa)).style("stroke", "var(--s3)");
        fa.g.selectAll("circle.g").data(g.gbm as number[]).join("circle").attr("cx", (_, k) => fa.x(gx[k])).attr("cy", (v) => fa.y(Math.max(-0.4, v))).attr("r", 4)
          .style("fill", "var(--s3)").style("stroke", "var(--surface)").style("stroke-width", 2);
        series.push({ label: "GBM forecast", color: "var(--s3)", xs: gx, ys: g.gbm, fmt: (v: number) => `${fmt(v * 100, 0)} %` });
      }
    } else gbmNote = " GBM forecast: default scenario only.";
    fa.g.append("line").attr("x1", fa.x(times[i])).attr("x2", fa.x(times[i])).attr("y1", 0).attr("y2", fa.h).style("stroke", "var(--ink)");
    crosshair(fa, () => series, tf);

    legendBox.replaceChildren(legend([
      { label: "simulated margin", color: "var(--s1)" },
      { label: "physics forecast", color: "var(--s2)", kind: "dash" },
      ...(state.isDefault ? [{ label: "GBM forecast", color: "var(--s3)" }] : []),
    ]));

    // ---- B: gauge water level + events
    chartB.replaceChildren();
    const gw = d3.range(w0, w1 + 1);
    const gwT = gw.map((k) => times[k]);
    const gy = gw.map((k) => T.gauge_water_mm[k]);
    const fb = frame(chartB, { width: 1120, height: 170, margin: { top: 6, right: 16, bottom: 30, left: 48 }, x: xDom.copy(), y: [0, Math.max(10, d3.max(gy)! * 1.15)], yLabel: "gauge: bottom layer, mm", xFormat: (t: Date) => d3.timeFormat("%d %b")(t) });
    fb.g.append("path").attr("class", "line").attr("d", linePath(gwT, gy, fb)).style("stroke", "var(--s1)").style("stroke-width", 1.5);
    if (state.isDefault) {
      for (const s of tw.changepoints_steps as number[]) {
        if (s < w0 || s > w1) continue;
        fb.g.append("line").attr("x1", fb.x(times[s])).attr("x2", fb.x(times[s])).attr("y1", 0).attr("y2", fb.h).style("stroke", "var(--s2)").style("stroke-width", 1.5).style("stroke-dasharray", "3 2");
      }
    }
    for (const e of run.events) {
      if (e.step < w0 || e.step > w1) continue;
      const mark = e.type === "separation_onset" ? "▼ separation" : e.type === "drain_out" ? "drain" : e.type === "delivery" && e.wet ? "wet tanker" : null;
      if (!mark) continue;
      fb.g.append("text").attr("class", "axis-label").attr("x", fb.x(times[e.step])).attr("y", 10).attr("text-anchor", "middle").style("fill", "var(--ink)").text(mark);
    }
    fb.g.append("line").attr("x1", fb.x(times[i])).attr("x2", fb.x(times[i])).attr("y1", 0).attr("y2", fb.h).style("stroke", "var(--ink)");
    crosshair(fb, () => [{ label: "bottom layer", color: "var(--s1)", xs: gwT, ys: gy, fmt: (v) => `${fmt(v, 1)} mm` }], tf);

    // ---- C: rain
    chartC.replaceChildren();
    const rp = gw.map((k) => T.precip_mm[k] * 2);
    const fcc = frame(chartC, { width: 1120, height: 110, margin: { top: 6, right: 16, bottom: 30, left: 48 }, x: xDom.copy(), y: [0, Math.max(2, d3.max(rp)! * 1.1)], yLabel: "rain, mm/h", yTicks: 3, xFormat: (t: Date) => d3.timeFormat("%d %b")(t) });
    fcc.g.selectAll("rect.r").data(rp).join("rect").attr("x", (_, k) => fcc.x(gwT[k])).attr("width", Math.max(1, fcc.w / gw.length - 0.5))
      .attr("y", (v) => fcc.y(v)).attr("height", (v) => fcc.h - fcc.y(v)).style("fill", "var(--water)");
    crosshair(fcc, () => [{ label: "rain", color: "var(--water)", xs: gwT, ys: rp, fmt: (v) => `${fmt(v, 1)} mm/h` }], tf);

    caption.innerHTML = `Dashed verticals: detected change points. The forecast is given the real rain record as a perfect forecast.${gbmNote}`;
  }

  let last = 0;
  function loop(t = 0) {
    if (!state.playing) return;
    if (t - last > 60) {
      last = t;
      state.cursor = state.cursor >= w1 ? w0 : state.cursor + 2;
      scrub.value = String(state.cursor);
      draw();
    }
    requestAnimationFrame(loop);
  }

  draw();
  inner.append(fig);
  return sec;
}
