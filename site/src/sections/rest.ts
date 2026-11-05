import * as d3 from "d3";
import type { Data } from "../lib/data";
import { badge, callout, chapter, details, figure, fmt, h, stat, table } from "../lib/ui";

export function system() {
  const { sec, inner } = chapter("system", 7, "How it fits together", "Layer A stops bad loads at the depot. Layer B watches each tank after delivery.", "The system");
  const card = h("div", { class: "card" });
  const W = 1000, H = 380;
  const svg = d3.select(card).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", "System diagram");
  svg.append("defs").append("marker").attr("id", "ah").attr("viewBox", "0 0 10 10").attr("refX", 9).attr("refY", 5).attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto")
    .append("path").attr("d", "M0 0 L10 5 L0 10 z").style("fill", "var(--axis)");
  const col = [30, 380, 730];
  const node = (x: number, y: number, w: number, title: string, sub: string, kind: "in" | "model" | "out", accent = "var(--ink)") => {
    const hh = 64;
    svg.append("rect").attr("x", x).attr("y", y).attr("width", w).attr("height", hh).attr("rx", 14)
      .style("fill", kind === "model" ? "var(--ink)" : "var(--sunk)");
    svg.append("text").attr("x", x + 18).attr("y", y + 27).style("font-size", "14px").style("font-weight", 600).style("fill", kind === "model" ? "var(--page)" : "var(--ink)").text(title);
    svg.append("text").attr("x", x + 18).attr("y", y + 47).style("font-size", "12px").style("fill", kind === "model" ? "var(--axis)" : "var(--ink-2)").text(sub);
    if (kind === "model") svg.append("circle").attr("cx", x + w - 20).attr("cy", y + 20).attr("r", 5).style("fill", accent);
    return { l: x, r: x + w, m: y + hh / 2 };
  };
  const a = (x1: number, y1: number, x2: number, y2: number) => {
    const mx = (x1 + x2) / 2;
    svg.append("path").attr("d", `M${x1} ${y1} C${mx} ${y1} ${mx} ${y2} ${x2 - 4} ${y2}`).style("stroke", "var(--axis)").style("stroke-width", 1.5).style("fill", "none").attr("marker-end", "url(#ah)");
  };
  const i1 = node(col[0], 20, 260, "Tanker sample spectrum", "Raman / NIR + lab labels", "in");
  const i2 = node(col[0], 110, 260, "Tank gauge, every 30 min", "level · bottom layer · temp", "in");
  const i3 = node(col[0], 200, 260, "Weather + forecast", "rain · temperature · humidity", "in");
  const i4 = node(col[0], 260 + 30, 260, "Drain-out records", "Solution 4: labelled data", "in");
  const mA = node(col[1], 20, 260, "Layer A · PLS", "ethanol, water ± error", "model", "var(--s1)");
  const mB = node(col[1], 170, 260, "Layer B · forecast", "margin to separation, 72 h", "model", "var(--s2)");
  const oA = node(col[2], 20, 240, "Release / re-test / reject", "before dispatch", "out");
  const oB = node(col[2], 170, 240, "SAFE · WATCH · ACT", "per tank, 24–48 h ahead", "out");
  a(i1.r, i1.m, mA.l, mA.m); a(mA.r, mA.m, oA.l, oA.m);
  for (const i of [i2, i3, i4]) a(i.r, i.m, mB.l, mB.m);
  a(mB.r, mB.m, oB.l, oB.m);
  svg.append("path").attr("d", `M${col[1] + 130} 86 L${col[1] + 130} 166`).style("stroke", "var(--axis)").style("stroke-width", 1.5).style("stroke-dasharray", "3 4").attr("marker-end", "url(#ah)");
  svg.append("text").attr("x", col[1] + 140).attr("y", 130).attr("class", "axis-label").text("water at delivery");
  inner.append(card);
  return sec;
}

export function results(d: Data) {
  const { sec, inner } = chapter("results", 8, "What we can claim", "Layer A is tested on real fuel. Layer B is a design study on simulated tanks.", "Results & limits");
  const A = d.resultsA.targets, B = d.metricsB, ev = B.evaluation;
  const r = (x: number | null | undefined, k = 2) => fmt(x ?? null, k);
  const n = ev.n_incidents;
  const caught = (k: string) => Math.round((ev[k].incident_recall ?? 0) * n);

  const ok = h("div", { class: "card" }, h("h3", {}, "Validated", h("span", { class: "badge real" }, "REAL DATA")),
    h("ul", { class: "clean ok" },
      h("li", { html: `Ethanol from a handheld Raman scan: <b>±${r(d.val.layerA.targets["Ethanol Content (%)"].nested_cv.rmsep_mean)} % v/v</b> (repeated nested CV), ±${r(A.ethanol.test.pls.rmsep)} on the held-out test` }),
      h("li", { html: `Ethanol at E20 by FTIR on lab blends: unseen E20 samples predicted at <b>${r(d.val.ftir.leave_E20_out.pred_mean, 1)} %</b>` }),
      h("li", { html: `Water-tolerance curve: within ${r(d.val.tolerance.correlation["E5-E30 (fuel-relevant)"].mape_pct, 0)} % of 21 measurements (E5–E30), on the safe side` })));
  const todo = h("div", { class: "card" }, h("h3", {}, "Not yet validated"),
    h("ul", { class: "clean todo" },
      h("li", { html: "Commercial Indian E20: Raman calibration spans <b>0–10 %</b>, FTIR used lab substitutes" }),
      h("li", { html: "Water by Raman: fails, because the O–H band is out of range" }),
      h("li", { html: "Every Layer B number: simulated tanks. No public tank-gauge data exists" })));
  inner.append(h("div", { class: "grid2", style: "margin-bottom:20px" }, ok, todo));

  const { fig, body } = figure(`Forecast models on ${B.fleet.test.tanks} test tanks · ${n} separations`, ["SYNTHETIC (physics-informed)"], "trained on 2022–23 weather, tested on 2024");
  const rows: [string, string][] = [["legacy_xgboost", "Original XGBoost"], ["physics_rollforward", "Physics roll-forward"], ["gbm", "Gradient-boosted"]];
  body.append(table(["model", "caught", "median warning", "alerts correct", "error at 72 h"], rows.map(([k, name]) => {
    const m = ev[k];
    return [k === "gbm" ? `<b>${name}</b>` : name, `${caught(k)} / ${n}`, m.lead_time_h_median === null ? "–" : `${r(m.lead_time_h_median, 0)} h`,
      m.act_precision === null ? "–" : `${r(m.act_precision * 100, 0)} %`, r(m.margin_mae_by_h["72"], 3)];
  }), { numeric: [1, 2, 3, 4] }));
  body.append(h("p", { class: "note", style: "margin:12px 0 0", html: `${badge("ASSUMPTION").outerHTML} Depends on assumed leak sizes, dissolution rate and tank turnover. Read it as a comparison of methods, not field performance.` }));
  inner.append(fig);

  const s4 = B.solution4.by_seal.major, bo = B.breathing_only, cr = B.changepoints.recon.test;
  inner.append(h("div", { class: "grid3" },
    stat(`${bo.tanks_separated} / ${bo.sealed_tanks}`, "sealed tanks that separated from breathing alone, which agrees with EPA (1995)", "SYNTHETIC (physics-informed)"),
    stat(`${s4.tanks_with_separation_off} → ${s4.tanks_with_separation_on}`, `leaking tanks (of ${s4.tanks}) that separate, without and with weekly drain-outs`, "SYNTHETIC (physics-informed)"),
    stat(`${Math.round(cr.recall * 100)} %`, `of separations spotted by volume reconciliation within ~${r(cr.mean_abs_delay_h, 0)} h. Detection, not forecast`, "SYNTHETIC (physics-informed)"),
  ));

  const cpw = B.changepoints.water.test;
  inner.append(details("Change points, split and metric definitions", h("div", {},
    table(["stream", "detector", "precision", "recall", "F1"], [
      ["gauge: bottom layer", B.changepoints.water.detector, r(cpw.precision), r(cpw.recall), r(cpw.f1)],
      ["volume loss (gauge − book)", B.changepoints.recon.detector, r(cr.precision), r(cr.recall), r(cr.f1)],
    ], { numeric: [2, 3, 4] }),
    h("p", { class: "note", html: `"Caught" means an ACT alert came before onset. "Alerts correct" means separation followed within 48 h. The GBM alerts on its 10th-percentile forecast.
      No tank or weather year is shared between training and test. Water mass balance closes to ~10⁻¹¹ kg in every tank.` })), "SYNTHETIC"));
  inner.append(callout("→", `<b>To validate Layer B</b> we need OMC gauge logs, delivery records and drain-out volumes from real tanks through one monsoon.`));
  return sec;
}

export function sources(d: Data) {
  const S = d.sources;
  const nAss = S.entries.filter((e: any) => e.label === "ASSUMPTION").length;
  const { sec, inner } = chapter("sources", 10, "Sources & assumptions", `Every number lives in one file with a citation. ${nAss} are assumptions that still need checking.`, "Sources");

  const filter = h("div", { class: "seg", role: "group", "aria-label": "Filter by label", style: "margin-bottom:12px" });
  const box = h("div");
  const render = (want: string) => {
    const pick = S.entries.filter((e: any) => want === "all" || e.label === want);
    const v = (e: any) => (typeof e.value === "object" ? `<code>${JSON.stringify(e.value).replace(/,/g, ", ")}</code>` : String(e.value));
    const rows = pick.map((e: any) => [`<code>${e.key}</code>`, v(e), e.unit ?? "",
      e.label === "ASSUMPTION" ? (e.note ?? "") : `${e.source ?? ""}${want === "all" ? ` <span class="fig-sub">· ${e.label.toLowerCase()}</span>` : ""}`]);
    box.replaceChildren(table(["key", "value", "unit", want === "ASSUMPTION" ? "why it matters" : "source"], rows));
  };
  for (const l of ["ASSUMPTION", "STANDARD", "LITERATURE VALUE", "PHYSICAL CONSTANT", "DESIGN CHOICE", "all"]) {
    const b = h("button", { "aria-pressed": String(l === "ASSUMPTION") }, l === "all" ? "all" : l.toLowerCase());
    b.addEventListener("click", () => { filter.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); render(l); });
    filter.append(b);
  }
  render("ASSUMPTION");
  inner.append(details("Constants and assumptions", h("div", {}, filter, box), `${S.entries.length} entries · config/constants.yaml`, true));

  const ol = h("ol", { style: "font-size:0.84rem;line-height:1.6;padding-left:20px;margin:0" });
  for (const rf of S.references) {
    const link = rf.doi ? ` <a href="https://doi.org/${rf.doi}">doi</a>` : rf.url ? ` <a href="${rf.url}">link</a>` : "";
    ol.append(h("li", { html: `${rf.title}. <span class="fig-sub">${rf.journal ?? rf.institution ?? ""} ${rf.year ?? ""}</span>${link}` }));
  }
  inner.append(details("References", ol, `${S.references.length} sources`));

  const m = S.meta;
  inner.append(details("Reproduce", h("div", {},
    h("pre", {}, `pip install -r requirements.txt
make all        # data → Layer A → Layer B → site JSON → tests
make preview    # http://localhost:4173`),
    h("p", { class: "note", style: "margin-top:14px", html: `Python ${m.python} · ${Object.entries(m.packages).map(([k, v]) => `${k} ${v}`).join(" · ")}. Seeds fixed. Dataset: <a href="${m.dataset}">FuelRamanSpectraHandheld</a>, CC-BY-4.0.` })),
    "one command"));
  return sec;
}
