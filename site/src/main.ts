import "./styles.css";
import { loadAll, type Data } from "./lib/data";
import { waterToleranceWtPct, pctVvToMgPerKg } from "./lib/sim";
import { val } from "./lib/data";
import { fmt, h, stat } from "./lib/ui";
import { chain } from "./sections/chain";
import { layerA } from "./sections/layerA";
import { physics } from "./sections/physics";
import { playground } from "./sections/playground";
import { problem } from "./sections/problem";
import { results, sources, system } from "./sections/rest";
import { twin } from "./sections/twin";
import { validation } from "./sections/validation";

function hero(d: Data) {
  const ethCv = d.val.layerA.targets["Ethanol Content (%)"].nested_cv;
  const gbm = d.metricsB.evaluation.gbm;
  const tol20 = waterToleranceWtPct(d.constants, 20, 20);
  const ratio = (tol20 * 1e4) / pctVvToMgPerKg(d.constants, val(d.constants, "spec", "e20_max_water_content"));
  return h("section", { class: "hero", id: "top" },
    h("div", { class: "wrap" },
      h("div", { class: "hero-grid" },
        h("div", {},
          h("div", { class: "eyebrow" }, "Chemical engineering · progress review II"),
          h("h1", { html: "Keeping <em>water</em> out of E20" }),
          h("p", { class: "dek" }, "An early-warning system for India's ethanol-blended petrol: a spectrum check at the depot, and a forecast for every tank.")),
        heroArt()),
      h("div", { class: "stats" },
        stat(`±${fmt(ethCv.rmsep_mean, 1)}%`, "ethanol error on real fuel samples, handheld Raman + PLS, repeated nested cross-validation", "REAL DATA"),
        stat(`${fmt(tol20, 1)} wt%`, `water E20 holds at 20 °C before it separates, about ${Math.round(ratio)}× its quality limit`, "LITERATURE VALUE"),
        stat(`${fmt(gbm.lead_time_h_median, 0)} h`, `median warning before separation, ${Math.round(gbm.incident_recall * d.metricsB.evaluation.n_incidents)} of ${d.metricsB.evaluation.n_incidents} incidents caught in simulated tanks`, "SYNTHETIC (physics-informed)"),
      ),
    ),
  );
}

function heroArt() {
  const ns = "http://www.w3.org/2000/svg";
  const wrap = h("div", { class: "hero-art", "aria-hidden": "true" });
  wrap.innerHTML = `<svg viewBox="0 0 400 400" xmlns="${ns}">
    <defs><clipPath id="hc"><circle cx="200" cy="200" r="150"/></clipPath></defs>
    <g clip-path="url(#hc)">
      <rect x="0" y="0" width="400" height="400" style="fill:var(--vapour)"/>
      <g class="fuel"><path d="M0 190 Q100 180 200 190 T400 190 L400 400 L0 400Z" style="fill:var(--fuel)"/></g>
      <rect class="lower" x="0" y="296" width="400" height="60" style="fill:var(--lower)"/>
      ${Array.from({ length: 14 }, (_, i) => `<circle class="drop" cx="${70 + ((i * 47) % 260)}" cy="${215 + ((i * 31) % 60)}" r="${2 + (i % 3)}" style="fill:var(--water);animation-delay:${(i * 0.7).toFixed(1)}s"/>`).join("")}
    </g>
    <circle cx="200" cy="200" r="150" style="fill:none;stroke:var(--ink);stroke-width:1.5"/>
    <text x="200" y="120" text-anchor="middle" class="axis-label">vapour</text>
    <text x="200" y="250" text-anchor="middle" class="direct-label">E20</text>
    <text x="200" y="334" text-anchor="middle" style="fill:#fff;font-size:12px;font-weight:600">ethanol–water layer</text>
  </svg>`;
  return wrap;
}

function navSpy() {
  const links = [...document.querySelectorAll<HTMLAnchorElement>(".nav a")];
  const bar = document.querySelector<HTMLDivElement>(".progress")!;
  const targets = links.map((a) => document.querySelector<HTMLElement>(a.getAttribute("href")!)!);
  const onScroll = () => {
    const y = window.scrollY + 120;
    let k = -1;
    targets.forEach((t, i) => { if (t && t.offsetTop <= y) k = i; });
    links.forEach((a, i) => a.classList.toggle("on", i === k));
    const max = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.width = `${Math.min(100, (window.scrollY / Math.max(1, max)) * 100)}%`;
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

async function main() {
  const app = document.getElementById("app")!;
  try {
    const d = await loadAll();
    app.replaceChildren(hero(d), problem(d), chain(), physics(d), layerA(d), playground(d), twin(d), system(), results(d), validation(d), sources(d));
    navSpy();
  } catch (e) {
    app.innerHTML = `<p class="wrap loading">Could not load the data files (${(e as Error).message}). Run <code>make all</code>.</p>`;
    throw e;
  }
}
main();
