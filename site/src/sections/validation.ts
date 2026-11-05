import * as d3 from "d3";
import type { Data } from "../lib/data";
import { frame } from "../lib/chart";
import { badge, callout, chapter, details, figure, fmt, h, legend, stat, table, tip } from "../lib/ui";

const ETH = "Ethanol Content (%)";

export function validation(d: Data) {
  const { sec, inner } = chapter("validation", 9, "How we checked it", "Every claim tested more than one way, on every real dataset we could find.", "Validation");
  const V = d.val;
  const eth = V.layerA.targets[ETH];
  const ft = V.ftir;
  const tol = V.tolerance;

  inner.append(h("div", { class: "stats", style: "margin-bottom:20px" },
    stat(`±${fmt(eth.nested_cv.rmsep_mean, 2)}%`, `ethanol error over ${eth.nested_cv.repeats}× repeated nested cross-validation of all ${eth.n_dev + eth.n_test} Raman samples`, "REAL DATA"),
    stat(`${fmt(ft.leave_E20_out.pred_mean, 1)}%`, `predicted for ${ft.leave_E20_out.n} real E20 blends the FTIR model never saw (± ${fmt(ft.leave_E20_out.rmsep, 1)})`, "REAL DATA"),
    stat(`${fmt(tol.correlation.korotney1995.mape_pct, 0)} %`, `error of our water-tolerance curve against the measured EPA/API E10 curve`, "LITERATURE VALUE"),
  ));

  // ---- 1. tolerance: predicted vs measured
  const grid = h("div", { class: "grid2" });
  {
    const { fig, body, caption } = figure("Water tolerance: our curve vs measurements", ["LITERATURE VALUE"], `${tol.n} measured points, 3 independent studies`);
    const pts: any[] = tol.points.filter((p: any) => p.ethanol_vol_pct <= 50);
    const mx = d3.max(pts, (p: any) => Math.max(p.water_wt_pct, p.corr_pred))! * 1.08;
    const f = frame(body, { width: 480, height: 380, margin: { top: 8, right: 16, bottom: 40, left: 44 }, x: d3.scaleLinear().domain([0, mx]), y: [0, mx], xLabel: "measured, wt %", yLabel: "our curve, wt %" });
    f.g.append("line").attr("x1", f.x(0)).attr("x2", f.x(mx)).attr("y1", f.y(0)).attr("y2", f.y(mx)).style("stroke", "var(--axis)").style("stroke-dasharray", "4 4");
    f.g.append("text").attr("class", "axis-label").attr("x", f.x(mx) - 4).attr("y", f.y(mx) + 14).attr("text-anchor", "end").text("perfect");
    f.g.append("text").attr("class", "axis-label").attr("x", f.x(mx * 0.62)).attr("y", f.y(mx * 0.32)).text("below the line = conservative");
    const col: Record<string, string> = { johansen2009: "var(--s1)", korotney1995: "var(--s2)", haq1990: "var(--s3)" };
    const name: Record<string, string> = { johansen2009: "Johansen & Schramm 2009", korotney1995: "EPA / API E10 curve", haq1990: "Haq & Ali 1990" };
    f.g.selectAll("circle").data(pts).join("circle").attr("cx", (p) => f.x(p.water_wt_pct)).attr("cy", (p) => f.y(p.corr_pred)).attr("r", 5)
      .style("fill", (p) => col[p.source]).style("stroke", "var(--surface)").style("stroke-width", 2)
      .on("pointermove", (ev, p) => tip(`${name[p.source]}<br>E${fmt(p.ethanol_vol_pct, 0)} at ${fmt(p.temp_c, 0)} °C<br><span class="k">measured</span> <b>${fmt(p.water_wt_pct, 2)}</b> · <span class="k">curve</span> <b>${fmt(p.corr_pred, 2)}</b> wt %`, ev))
      .on("pointerleave", () => tip(null));
    body.prepend(legend(Object.keys(col).map((k) => ({ label: name[k], color: col[k], kind: "box" as const }))));
    const c = tol.correlation["E5-E30 (fuel-relevant)"];
    caption.textContent = `E5–E30: within ${fmt(c.mape_pct, 0)} % on average, and slightly low near E20, which is the safe side. A curve refitted to these points did worse in cross-validation, so we kept the published one.`;
    grid.append(fig);
  }
  // ---- 2. FTIR E0-E90 parity
  {
    const { fig, body, caption } = figure("Ethanol by FTIR, 0–90 % blends", ["REAL DATA"], `${ft.n_samples} lab-prepared spectra · grouped cross-validation`);
    const ref: number[] = ft.parity.ref, oof: number[] = ft.parity.oof;
    const f = frame(body, { width: 480, height: 380, margin: { top: 8, right: 16, bottom: 40, left: 44 }, x: d3.scaleLinear().domain([0, 92]), y: [-5, 95], xLabel: "prepared, % v/v", yLabel: "predicted, % v/v" });
    f.g.append("line").attr("x1", f.x(0)).attr("x2", f.x(92)).attr("y1", f.y(0)).attr("y2", f.y(92)).style("stroke", "var(--axis)").style("stroke-dasharray", "4 4");
    f.g.append("rect").attr("x", f.x(15)).attr("width", f.x(25) - f.x(15)).attr("y", 0).attr("height", f.h).style("fill", "var(--s2-wash)");
    f.g.append("text").attr("class", "axis-label").attr("x", f.x(20)).attr("y", 12).attr("text-anchor", "middle").text("E20 band");
    f.g.selectAll("circle.o").data(d3.range(ref.length)).join("circle").attr("cx", (i) => f.x(ref[i])).attr("cy", (i) => f.y(oof[i])).attr("r", 4)
      .style("fill", "var(--s1)").style("opacity", 0.75).style("stroke", "var(--surface)").style("stroke-width", 1.5)
      .on("pointermove", (ev, i) => tip(`${ft.parity.id[i]}<br>${ft.parity.family[i]}<br><span class="k">prepared</span> <b>${ref[i]}</b> · <span class="k">predicted</span> <b>${fmt(oof[i], 1)}</b>`, ev))
      .on("pointerleave", () => tip(null));
    const g = ft.grouped_cv;
    caption.textContent = `All blends: R² ${fmt(g.all.r2, 3)}, ±${fmt(g.all.rmsep, 1)} % v/v. E15–E25: ±${fmt(g["E15-E25"].rmsep, 1)} % v/v. These are gasoline substitutes (heptane, isooctane, toluene…), not commercial fuel.`;
    grid.append(fig);
  }
  inner.append(grid);

  // ---- 3. Layer B: cities + stress
  const B = V.layerB;
  if (B) {
    const rows = [...Object.entries(B.cities).map(([k, v]) => ({ k: k[0].toUpperCase() + k.slice(1), v: v as any, group: "city" })),
      ...Object.entries(B.stress).filter(([k]) => !k.startsWith("baseline")).map(([k, v]) => ({ k, v: v as any, group: "stress" }))];
    const { fig, body, caption } = figure("Layer B on other cities and wrong assumptions", ["SYNTHETIC (physics-informed)", "REAL DATA (ERA5 reanalysis)"],
      `95 % CIs · trained on Varanasi 2022–23 only · ${B.tanks_per_scenario} tanks per row`);
    const W = 1120, rowH = 36, top = 40, H = top + rows.length * rowH + 50, left = 290, gap = 50;
    const pw = (W - left - gap - 20) / 2;
    const svg = d3.select(body).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img");
    const panels = [{ key: "incident_recall", title: "INCIDENTS CAUGHT BEFORE ONSET", x0: left }, { key: "act_precision", title: "ACT ALERTS THAT WERE RIGHT", x0: left + pw + gap }] as const;
    for (const pn of panels) {
      const x = d3.scaleLinear().domain([0, 1]).range([pn.x0, pn.x0 + pw]);
      svg.append("g").attr("class", "grid").attr("transform", `translate(0,${H - 34})`).call(d3.axisBottom(x).ticks(4).tickSize(-(H - 34 - top + 10)).tickFormat(() => "") as any);
      svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - 34})`).call(d3.axisBottom(x).ticks(4).tickFormat((v) => `${Math.round(+v * 100)} %`) as any);
      svg.append("text").attr("x", pn.x0).attr("y", 14).attr("class", "axis-label").text(pn.title);
      rows.forEach((r, i) => {
        const y = top + i * rowH + rowH / 2 + (r.group === "stress" ? 18 : 0);
        for (const [m, color, dy] of [["gbm", "var(--s3)", -9], ["physics_rollforward", "var(--s2)", 0], ["ensemble", "var(--s1)", 9]] as const) {
          const st = r.v[m];
          if (!st || st[pn.key] === null || st[pn.key] === undefined) continue;
          const ci = st.ci95?.[pn.key];
          if (ci) svg.append("line").attr("x1", x(ci[0])).attr("x2", x(ci[1])).attr("y1", y + dy).attr("y2", y + dy).style("stroke", color).style("stroke-width", 2).style("opacity", 0.4).style("stroke-linecap", "round");
          svg.append("circle").attr("cx", x(st[pn.key])).attr("cy", y + dy).attr("r", 4.5).style("fill", color).style("stroke", "var(--surface)").style("stroke-width", 2)
            .on("pointermove", (ev) => tip(`${r.k} · ${m === "gbm" ? "GBM" : m === "ensemble" ? "ensemble (both agree)" : "physics"}<br><span class="k">caught</span> <b>${fmt(st.incident_recall * 100, 0)} %</b><br><span class="k">alerts right</span> <b>${st.act_precision === null ? "–" : fmt(st.act_precision * 100, 0) + " %"}</b><br><span class="k">median lead</span> <b>${st.lead_time_h_median === null ? "–" : fmt(st.lead_time_h_median, 0) + " h"}</b>`, ev))
            .on("pointerleave", () => tip(null));
        }
      });
    }
    rows.forEach((r, i) => {
      const y = top + i * rowH + rowH / 2 + (r.group === "stress" ? 18 : 0);
      svg.append("text").attr("x", left - 14).attr("y", y + 4).attr("text-anchor", "end").attr("class", "direct-label").text(`${r.k}  (${r.v.n_incidents})`);
    });
    const nCity = Object.keys(B.cities).length;
    svg.append("text").attr("x", 0).attr("y", top - 4).attr("class", "axis-label").text("REAL 2024 WEATHER, 6 CITIES");
    svg.append("text").attr("x", 0).attr("y", top + nCity * rowH + 16).attr("class", "axis-label").text("VARANASI, ASSUMPTIONS DELIBERATELY WRONG");
    body.prepend(legend([{ label: "gradient-boosted", color: "var(--s3)", kind: "box" }, { label: "physics roll-forward", color: "var(--s2)", kind: "box" },
      { label: "ensemble: ACT when both agree", color: "var(--s1)", kind: "box" }]));
    caption.innerHTML = `Number in brackets: separation incidents in that test fleet. Hover for alert precision and lead time. ${badge("ASSUMPTION").outerHTML} still simulated tanks.`;
    inner.append(fig);
    const med = (m: string, k: string) => d3.median(Object.values(B.cities).map((c: any) => c[m]?.[k]).filter((x: any) => x != null) as number[]) ?? 0;
    const pc = (x: number) => `${Math.round(x * 100)} %`;
    inner.append(callout("→", `<b>Across the six cities</b> (medians): gradient-boosted catches ${pc(med("gbm", "incident_recall"))} but only ${pc(med("gbm", "act_precision"))} of its alerts are right, and it over-alerts in wetter climates it never saw.
      Physics catches ${pc(med("physics_rollforward", "incident_recall"))} with ${pc(med("physics_rollforward", "act_precision"))} right. Requiring both to agree gives the most trustworthy alarm (${pc(med("ensemble", "act_precision"))} right) at the cost of catching ${pc(med("ensemble", "incident_recall"))}.
      Recommended use: <b>physics or ensemble for ACT</b>, gradient-boosted for WATCH.`));
  } else {
    inner.append(h("p", { class: "note" }, "Layer B validation results are not generated yet (run make validate)."));
  }

  // ---- details
  const T = V.layerA.targets;
  const props = Object.entries(T).filter(([, e]: any) => !e.skipped).map(([k, e]: any) => [k, e.n_test, fmt(e.test.r2, 2), `${fmt(e.bootstrap_ci95.r2[0], 2)}–${fmt(e.bootstrap_ci95.r2[1], 2)}`, fmt(e.test.rpd, 1), `${fmt(e.pi_coverage_test * 100, 0)} %`]);
  inner.append(details("All 12 fuel properties from the same Raman spectra", table(["property", "test n", "R²", "95 % CI", "RPD", "inside error bar"], props, { numeric: [1, 2, 3, 4, 5] }), "REAL DATA"));
  const zoo = Object.entries(eth.models).map(([k, m]: any) => [k, fmt(m.r2, 3), fmt(m.rmsep, 2)]);
  const perm = eth.permutation;
  inner.append(details("Ethanol: model comparison, chance test, learning curve", h("div", {},
    table(["model (same preprocessing)", "test R²", "test RMSEP, % v/v"], zoo, { numeric: [1, 2] }),
    h("p", { class: "note", html: `<b>Chance test.</b> With the ethanol values shuffled ${perm.n_permutations} times, the best error was ${fmt(perm.null_rmsep_p05, 2)} (5th percentile) vs our ${fmt(perm.real_rmsep, 2)}: p = ${fmt(perm.p_value, 3)}.
      <b>Error bars</b> covered ${fmt(eth.nested_cv.pi_coverage * 100, 0)} % of samples in nested CV (target 95 %).
      <b>By grade (nested CV)</b>: ${Object.entries(eth.by_grade_nested).map(([g, v]: any) => `${g.split(" ")[0]} ±${fmt(v.rmsep, 2)}`).join(" · ")}. Error grows with ethanol, so expect more at E20.` }),
    learningCurve(eth.learning_curve)), "REAL DATA"));
  const lofo = Object.entries(ft.leave_one_family_out).map(([k, v]: any) => [k, v.n, fmt(v.rmsep, 2), fmt(v.bias, 2)]);
  inner.append(details("FTIR: whole fuel families held out", table(["held-out family", "n", "RMSEP, % v/v", "bias"], lofo, { numeric: [1, 2, 3] }),
    "REAL DATA"));
  return sec;
}

function learningCurve(lc: any[]) {
  const box = h("div");
  const f = frame(box, { width: 700, height: 200, margin: { top: 8, right: 16, bottom: 36, left: 44 }, x: d3.scaleLinear().domain([0, 135]), y: [0, d3.max(lc, (p) => p.rmsep_mean + p.rmsep_sd)! * 1.1], xLabel: "calibration samples", yLabel: "test error, % v/v" });
  const line = d3.line<any>().x((p) => f.x(p.n)).y((p) => f.y(p.rmsep_mean));
  f.g.append("path").attr("class", "line").attr("d", line(lc) ?? "").style("stroke", "var(--s1)");
  f.g.selectAll("circle").data(lc).join("circle").attr("cx", (p) => f.x(p.n)).attr("cy", (p) => f.y(p.rmsep_mean)).attr("r", 4).style("fill", "var(--s1)").style("stroke", "var(--surface)").style("stroke-width", 2);
  f.g.append("text").attr("class", "direct-label").attr("x", f.x(lc[lc.length - 1].n) - 6).attr("y", f.y(lc[lc.length - 1].rmsep_mean) - 10).attr("text-anchor", "end").text("still improving: more samples help");
  return box;
}
