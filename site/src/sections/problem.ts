import * as d3 from "d3";
import type { Data } from "../lib/data";
import { frame, linePath } from "../lib/chart";
import { badge, chapter, fmt, h, scrolly } from "../lib/ui";

const EXAGGERATION = 12; // vertical exaggeration of the bottom layers, stated on the figure

export function problem(d: Data) {
  const { sec, inner } = chapter("problem", 1, "A tank that breathes", "Ethanol holds water until it can't. Then a second layer forms at the bottom, right where the pump draws from.", "The problem");
  const tw = d.twin;
  const T = tw.trace;
  const cap = tw.params.capacity_m3 as number;
  const times: Date[] = tw.times.map((s: string) => new Date(s));
  const [w0, w1] = tw.window_steps as [number, number];
  const onset = (tw.events as any[]).find((e) => e.type === "separation_onset" && e.step >= w0);
  const onsetStep: number = onset ? onset.step : w1;
  const firstRain = (() => { for (let i = w0; i < w1; i++) if (T.ingress_liquid_kg[i] > 0.05) return i; return w0 + 96; })();

  // ---------- tank cross-section
  const W = 640, H = 380, cx = 320, cy = 238, R = 118, ground = 88;
  const svg = d3.create("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", "Cross-section of an underground fuel tank");
  svg.append("rect").attr("x", 0).attr("y", ground).attr("width", W).attr("height", H - ground).attr("rx", 12).style("fill", "var(--sunk)");
  svg.append("rect").attr("x", cx + 70).attr("y", 18).attr("width", 6).attr("height", cy - R - 18 + 40).attr("rx", 3).style("fill", "var(--axis)");
  svg.append("text").attr("x", cx + 84).attr("y", 30).attr("class", "axis-label").text("vent");
  svg.append("rect").attr("x", cx - 62).attr("y", ground - 6).attr("width", 36).attr("height", 8).attr("rx", 3).style("fill", "var(--axis)");
  svg.append("rect").attr("x", cx - 48).attr("y", ground).attr("width", 8).attr("height", cy - R - ground + 30).style("fill", "var(--axis)");
  svg.append("text").attr("x", cx - 70).attr("y", ground - 14).attr("text-anchor", "end").attr("class", "axis-label").text("fill cap");
  svg.append("clipPath").attr("id", "tankclip").append("circle").attr("cx", cx).attr("cy", cy).attr("r", R);
  const tank = svg.append("g").attr("clip-path", "url(#tankclip)");
  tank.append("rect").attr("x", cx - R).attr("y", cy - R).attr("width", 2 * R).attr("height", 2 * R).style("fill", "var(--vapour)");
  const fuelRect = tank.append("rect").attr("x", cx - R).attr("width", 2 * R).style("fill", "var(--fuel)");
  const lowerRect = tank.append("rect").attr("x", cx - R).attr("width", 2 * R).style("fill", "var(--lower)");
  const bottomRect = tank.append("rect").attr("x", cx - R).attr("width", 2 * R).style("fill", "var(--water)");
  svg.append("circle").attr("cx", cx).attr("cy", cy).attr("r", R).style("fill", "none").style("stroke", "var(--ink)").style("stroke-width", 1.5);
  const lblUllage = svg.append("text").attr("x", cx).attr("text-anchor", "middle").attr("class", "direct-label");
  const lblFuel = svg.append("text").attr("x", cx).attr("text-anchor", "middle").attr("class", "direct-label");
  const lblBottom = svg.append("text").attr("x", cx + R + 14).attr("class", "direct-label");
  svg.append("text").attr("x", cx + R + 14).attr("y", cy + R).attr("class", "axis-label").text(`bottom layers ×${EXAGGERATION}`);
  const arrows = svg.append("g"), rain = svg.append("g");
  const clock = svg.append("text").attr("x", 16).attr("y", H - 16).attr("class", "axis-label").style("font-variant-numeric", "tabular-nums");

  // ---------- mini chart
  const miniBox = h("div");
  const xs = d3.range(w0, w1 + 1);
  const xsT = xs.map((i) => times[i].getTime());
  const total = xs.map((i) => T.dissolved_kg[i] + T.bottom_kg[i] + T.lower_water_kg[i]);
  const tol = xs.map((i) => T.tolerance_kg[i]);
  const mini = frame(miniBox, {
    width: 640, height: 170, margin: { top: 8, right: 104, bottom: 26, left: 40 },
    x: d3.scaleLinear().domain([xsT[0], xsT[xsT.length - 1]]), y: [0, (d3.max([...total, ...tol]) as number) * 1.1],
    yLabel: "water, kg", xTicks: 6, yTicks: 3, xFormat: (t: number) => d3.timeFormat("%d %b")(new Date(t)),
  });
  mini.g.append("path").attr("class", "line").attr("d", linePath(xsT, tol, mini)).style("stroke", "var(--s3)");
  mini.g.append("path").attr("class", "line").attr("d", linePath(xsT, total, mini)).style("stroke", "var(--s1)");
  mini.g.append("text").attr("class", "direct-label").attr("x", mini.w + 8).attr("y", mini.y(tol[tol.length - 1]) + 4).text("fuel can hold");
  mini.g.append("text").attr("class", "direct-label").attr("x", mini.w + 8).attr("y", mini.y(total[total.length - 1]) + 4).text("water in tank");
  const cursor = mini.g.append("line").attr("y1", 0).attr("y2", mini.h).style("stroke", "var(--ink)").style("stroke-width", 1);

  const readout = h("div", { class: "readouts" });
  const stickyFig = h("figure", { class: "fig" },
    h("div", { class: "fig-head" }, h("div", { class: "fig-title" }, "One simulated tank · Varanasi, monsoon 2024"),
      h("div", { class: "badges" }, badge("SYNTHETIC (physics-informed)"), badge("REAL DATA (ERA5 reanalysis)"))),
    svg.node() as SVGSVGElement, miniBox, readout);

  const sumDay = (a: number[], i: number) => { let s = 0; for (let k = Math.max(0, i - 47); k <= i; k++) s += a[k]; return s; };
  const tile = (l: string, v: string) => h("div", { class: "tile" }, h("div", { class: "label" }, l), h("div", { class: "value" }, v));

  function draw(i: number) {
    const fill = T.fuel_m3[i] / cap;
    const scaleH = (m3: number) => (m3 / cap) * 2 * R;
    const lowH = Math.max(scaleH(T.lower_phase_m3[i]) * EXAGGERATION, T.lower_phase_m3[i] > 0 ? 3 : 0);
    const botH = Math.max(scaleH(T.bottom_kg[i] / 997) * EXAGGERATION, T.bottom_kg[i] > 0.05 ? 2 : 0);
    const level = cy + R - fill * 2 * R;
    fuelRect.attr("y", level).attr("height", cy + R - level);
    lowerRect.attr("y", cy + R - lowH - botH).attr("height", lowH);
    bottomRect.attr("y", cy + R - botH).attr("height", botH);
    lblUllage.attr("y", cy - R + 36).text(`vapour · ${fmt(T.t_ullage[i], 1)} °C`);
    lblFuel.attr("y", Math.min(cy + R - 22, level + 24)).text(`E20 · ${fmt(T.fuel_m3[i], 1)} m³`);
    lblBottom.attr("y", cy + R - 18).text(T.lower_phase_m3[i] > 0 ? `ethanol–water layer` : T.bottom_kg[i] > 0.05 ? `settled water` : "");
    arrows.selectAll("*").remove();
    if (T.air_in_m3[i] > 1e-4) {
      const n = Math.min(5, 1 + Math.round(T.air_in_m3[i] * 8));
      for (let k = 0; k < n; k++) arrows.append("path").attr("d", `M${cx + 73} ${12 + k * 9} l0 6 l-3 -3 m3 3 l3 -3`).style("stroke", "var(--s1)").style("fill", "none").style("stroke-width", 1.5);
    }
    rain.selectAll("*").remove();
    if (T.precip_mm[i] > 0.05) for (let k = 0; k < 16; k++) {
      const x = 30 + ((k * 37) % 580), y = 6 + ((k * 23 + i * 7) % 68);
      rain.append("line").attr("x1", x).attr("x2", x - 3).attr("y1", y).attr("y2", y + 8).style("stroke", "var(--water)").style("stroke-width", 1.5).style("stroke-linecap", "round");
    }
    clock.text(d3.timeFormat("%d %b %Y · %H:%M")(times[i]));
    cursor.attr("x1", mini.x(times[i].getTime())).attr("x2", mini.x(times[i].getTime()));
    readout.replaceChildren(
      tile("From humid air, today", `${fmt(sumDay(T.ingress_vapour_kg, i) * 1000, 0)} g`),
      tile("From rain via leak, today", `${fmt(sumDay(T.ingress_liquid_kg, i), 1)} kg`),
      tile("Margin to separation", T.margin[i] > 0 ? `${fmt(T.margin[i] * 100, 0)} %` : "separated"),
    );
  }

  let raf = 0;
  function play(a: number, b: number, seconds: number, loop = false) {
    cancelAnimationFrame(raf);
    const t0 = performance.now();
    const tick = (t: number) => {
      const u = Math.min(1, (t - t0) / (seconds * 1000));
      draw(Math.round(a + (b - a) * u));
      if (u < 1) raf = requestAnimationFrame(tick);
      else if (loop) play(a, b, seconds, loop);
    };
    raf = requestAnimationFrame(tick);
  }
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const steps: [number, number, number, boolean][] = [
    [w0, w0, 0.1, false],
    [w0, w0 + 48 * 3, 9, true],
    [Math.max(w0, firstRain - 12), Math.min(w1, firstRain + 96), 8, false],
    [w0, onsetStep + 12, 10, false],
    [onsetStep, w1, 6, false],
  ];
  const vapourDay = d3.mean(d3.range(w0, w1, 48).map((i) => sumDay(T.ingress_vapour_kg, i + 47))) ?? 0;
  const { root, sticky } = scrolly(
    [
      ["Underground", "The fuel sits at soil temperature. The vapour space above it is open to the air through a vent."],
      ["Breathing", `Each cool night and every litre sold pull in humid air, about <b>${fmt(vapourDay * 1000, 0)} g</b> of water a day. Harmless on its own.`],
      ["A leaking cap", "Monsoon rain through a worn seal is different: kilograms of water in one storm, settling to the bottom."],
      ["The limit", "When the water in the tank (blue) crosses what the fuel can hold (green), the excess separates out."],
      ["The cost", "The new layer strips ethanol from the fuel and sits at the pump inlet. The goal is to see it coming <b>24–48 h ahead</b>."],
    ],
    (i) => { const [a, b, s, loop] = steps[i]; if (reduced) draw(b); else play(a, b, s, loop); },
  );
  sticky.append(stickyFig);
  inner.append(root);
  draw(w0);
  return sec;
}
