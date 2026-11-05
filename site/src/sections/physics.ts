import * as d3 from "d3";
import type { Data } from "../lib/data";
import { val } from "../lib/data";
import { frame, linePath } from "../lib/chart";
import { waterToleranceWtPct, pctVvToMgPerKg } from "../lib/sim";
import { callout, chapter, figure, fmt, h, legend, stat, tip } from "../lib/ui";

export function physics(d: Data) {
  const c = d.constants;
  const specMgKg = pctVvToMgPerKg(c, val(c, "spec", "e20_max_water_content"));
  const specWt = specMgKg / 1e4;
  const tol20 = waterToleranceWtPct(c, 20, 20);
  const { sec, inner } = chapter("physics", 3, "How much water is too much?", `Two limits that are easy to confuse, about ${Math.round(tol20 / specWt)}× apart.`, "Phase separation");

  inner.append(h("div", { class: "grid3" },
    stat("0.05 % v/v", `E20 <b>quality</b> limit, ≈ ${fmt(specMgKg, 0)} mg/kg. Above it the fuel is off-spec but still one phase. <span class="fig-sub">IS 17943:2022, row xix</span>`, "LITERATURE VALUE"),
    stat(`${fmt(tol20, 1)} wt %`, `E20 <b>separation</b> point at 20 °C. It falls as the fuel cools. <span class="fig-sub">US 8,268,629 B2 correlation</span>`, "LITERATURE VALUE"),
  ));
  inner.append(callout("!", `The original repo used <b>0.5 % (5,000 ppm)</b>. That limit is for water in <i>neat ethanol</i> before blending (IS 15464, clause 3.2), not for the blend.`));

  const { fig, body } = figure("Water tolerance vs fuel temperature", ["LITERATURE VALUE"], "Drag the dashed line");
  const temps = d3.range(-20, 45.01, 0.5);
  const e20 = temps.map((t) => waterToleranceWtPct(c, t, 20));
  const e10 = temps.map((t) => waterToleranceWtPct(c, t, 10));
  const f = frame(body, {
    width: 900, height: 380, margin: { top: 10, right: 118, bottom: 40, left: 48 },
    x: d3.scaleLinear().domain([-20, 45]), y: [0, 2.4], xLabel: "fuel temperature, °C", yLabel: "water, wt %",
  });
  const shade = f.g.append("path").style("fill", "var(--s2-wash)");
  f.g.append("path").attr("class", "line").attr("d", linePath(temps, e20, f)).style("stroke", "var(--s1)").style("stroke-width", 2.5);
  f.g.append("path").attr("class", "line").attr("d", linePath(temps, e10, f)).style("stroke", "var(--s1)").style("stroke-dasharray", "5 4").style("opacity", 0.55);
  f.g.append("line").attr("x1", 0).attr("x2", f.w).attr("y1", f.y(specWt)).attr("y2", f.y(specWt)).style("stroke", "var(--s3)").style("stroke-width", 2);
  const end = (y: number, t: string) => f.g.append("text").attr("class", "direct-label").attr("x", f.w + 8).attr("y", f.y(y) + 4).text(t);
  end(e20[e20.length - 1], "E20 limit");
  end(e10[e10.length - 1], "E10 limit");
  end(specWt, "quality limit");
  const checks = [
    { short: "EPA 1995 · E10", t: 15.6, w: (val(c, "water_tolerance", "e10_check_point") * val(c, "physical", "density_water")) / val(c, "physical", "density_e20") },
    { short: "Haq & Ali 1990 · E25", t: 0, w: d3.mean(val(c, "water_tolerance", "haq_e25_0c_check_point") as number[]) as number },
  ];
  for (const k of checks) {
    f.g.append("circle").attr("cx", f.x(k.t)).attr("cy", f.y(k.w)).attr("r", 5).style("fill", "var(--s2)").style("stroke", "var(--surface)").style("stroke-width", 2)
      .on("pointermove", (ev) => tip(`Measured: ${k.short}<br><b>${fmt(k.w, 2)} wt %</b>`, ev)).on("pointerleave", () => tip(null));
    f.g.append("text").attr("class", "axis-label").attr("x", f.x(k.t) + 9).attr("y", f.y(k.w) - 8).text(k.short);
  }
  let water = 1.5;
  const wl = f.g.append("line").attr("x1", 0).attr("x2", f.w).style("stroke", "var(--ink)").style("stroke-width", 2).style("stroke-dasharray", "6 5");
  const knob = f.g.append("circle").attr("cx", f.w).attr("r", 7).style("fill", "var(--ink)").style("stroke", "var(--surface)").style("stroke-width", 3);
  const handle = f.g.append("rect").attr("x", 0).attr("width", f.w + 10).attr("height", 22).style("fill", "transparent").style("cursor", "ns-resize");
  const out = h("div", { class: "readouts" });
  function update() {
    wl.attr("y1", f.y(water)).attr("y2", f.y(water));
    knob.attr("cy", f.y(water));
    handle.attr("y", f.y(water) - 11);
    const clipped = e20.map((v) => Math.min(v, water));
    shade.attr("d", d3.area<number>().x((_, i) => f.x(temps[i])).y0((_, i) => f.y(clipped[i])).y1(f.y(water))(temps) ?? "");
    const idx = e20.findIndex((v) => v >= water);
    const tCross = idx === 0 ? -Infinity : idx < 0 ? Infinity : temps[idx - 1] + ((water - e20[idx - 1]) / (e20[idx] - e20[idx - 1])) * 0.5;
    const tile = (l: string, v: string) => h("div", { class: "tile" }, h("div", { class: "label" }, l), h("div", { class: "value" }, v));
    out.replaceChildren(
      tile("Water in the tank", `${fmt(water, 2)} wt %`),
      tile("E20 separates below", Number.isFinite(tCross) ? `${fmt(tCross, 1)} °C` : tCross > 0 ? "always" : "never (on chart)"),
      tile("Times the quality limit", `${fmt(water / specWt, 0)}×`),
    );
  }
  handle.call(d3.drag<SVGRectElement, unknown>().on("drag", (ev) => { water = Math.max(0.05, Math.min(2.35, f.y.invert(ev.y))); update(); slider.value = String(water); }) as any);
  const slider = h("input", { type: "range", min: 0.05, max: 2.35, step: 0.01, value: water, "aria-label": "Water content, wt %", style: "width:100%" }) as HTMLInputElement;
  slider.addEventListener("input", () => { water = Number(slider.value); update(); });
  body.prepend(legend([
    { label: "E20", color: "var(--s1)" }, { label: "E10", color: "var(--s1)", kind: "dash" },
    { label: "quality limit", color: "var(--s3)" }, { label: "measured check points", color: "var(--s2)", kind: "box" },
    { label: "separates", color: "var(--s2-wash)", kind: "box" },
  ]));
  body.append(slider, out);
  update();
  inner.append(fig);
  return sec;
}
