export type DataLabel = "REAL DATA" | "SYNTHETIC (physics-informed)" | "LITERATURE VALUE" | "REAL DATA (ERA5 reanalysis)";

export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Record<string, string | number | boolean | undefined> = {},
  ...children: (Node | string | null | undefined)[]
): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === false) continue;
    if (k === "html") e.innerHTML = String(v);
    else e.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children) if (c != null) e.append(c);
  return e;
}

export function badge(label: DataLabel | string): HTMLSpanElement {
  const cls = label.startsWith("REAL") ? "real" : label.startsWith("SYNTH") ? "synth" : label.startsWith("ASSUMPTION") ? "assume" : "lit";
  return h("span", { class: `badge ${cls}` }, label);
}

export function figure(title: string, labels: (DataLabel | string)[], sub?: string) {
  const body = h("div", { class: "fig-body" });
  const caption = h("figcaption");
  const fig = h(
    "figure",
    { class: "fig" },
    h("div", { class: "fig-head" }, h("div", {}, h("div", { class: "fig-title" }, title), sub ? h("div", { class: "fig-sub" }, sub) : null), h("div", { class: "badges" }, ...labels.map(badge))),
    body,
    caption,
  );
  return { fig, body, caption };
}

export function chapter(id: string, n: number, title: string, dek?: string, kicker?: string) {
  const inner = h("div", { class: "wrap" },
    h("div", { class: "ch-head" },
      h("div", { class: "ch-num" }, `${String(n).padStart(2, "0")}${kicker ? ` · ${kicker}` : ""}`),
      h("h2", { html: title }),
      dek ? h("p", { class: "dek", html: dek }) : null));
  const sec = h("section", { class: "chapter", id }, inner);
  return { sec, inner };
}

export function stat(value: string, label: string, data: DataLabel | string) {
  return h("div", { class: "stat" }, h("div", { class: "v" }, value), h("div", { class: "l", html: label }), h("div", {}, badge(data)));
}

export function details(summary: string, body: Node, sub?: string, open = false) {
  return h("details", { class: "more", open }, h("summary", {}, summary, sub ? h("span", { class: "fig-sub" }, sub) : null), h("div", { class: "body" }, body));
}

export function callout(icon: string, html: string) {
  return h("div", { class: "callout" }, h("span", { class: "ic" }, icon), h("div", { html }));
}

export function prose(html: string) {
  return h("div", { class: "prose", html });
}

/** Scrollytelling: sticky graphic + steps; onStep fires with the active index. */
export function scrolly(steps: [string, string][] | string[], onStep: (i: number) => void) {
  const sticky = h("div", { class: "sticky" });
  const stepsEl = h("div", { class: "steps" });
  const els = steps.map((st, i) => {
    const html = Array.isArray(st) ? `<span class="k">${st[0]}</span>${st[1]}` : st;
    const s = h("div", { class: "step", "data-i": i }, h("div", { html }));
    stepsEl.append(s);
    return s;
  });
  const root = h("div", { class: "scrolly" }, sticky, stepsEl);
  let current = -1;
  const io = new IntersectionObserver(
    (entries) => {
      for (const en of entries) {
        if (!en.isIntersecting) continue;
        const i = Number((en.target as HTMLElement).dataset.i);
        if (i === current) continue;
        current = i;
        els.forEach((e, k) => e.classList.toggle("active", k === i));
        onStep(i);
      }
    },
    { rootMargin: "-45% 0px -45% 0px" },
  );
  els.forEach((e) => io.observe(e));
  return { root, sticky };
}

let tipEl: HTMLDivElement | null = null;
export function tip(html: string | null, ev?: { clientX: number; clientY: number }) {
  if (!tipEl) {
    tipEl = h("div", { class: "tip", role: "status" });
    document.body.append(tipEl);
  }
  if (html === null || !ev) {
    tipEl.style.opacity = "0";
    return;
  }
  tipEl.innerHTML = html;
  const pad = 14;
  const w = tipEl.offsetWidth, hh = tipEl.offsetHeight;
  let x = ev.clientX + pad, y = ev.clientY + pad;
  if (x + w > window.innerWidth - 8) x = ev.clientX - w - pad;
  if (y + hh > window.innerHeight - 8) y = ev.clientY - hh - pad;
  tipEl.style.left = `${x}px`;
  tipEl.style.top = `${y}px`;
  tipEl.style.opacity = "1";
}

export function legend(items: { label: string; color: string; kind?: "line" | "dash" | "box" }[]) {
  return h(
    "div",
    { class: "legend" },
    ...items.map((it) => h("span", {}, h("span", { class: `key ${it.kind ?? ""}`, style: `background:${it.color};color:${it.color}` }), it.label)),
  );
}

export const fmt = (x: number | null | undefined, d = 2) =>
  x === null || x === undefined || !Number.isFinite(x) ? "–" : x.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });

export function table(head: string[], rows: (string | number | null)[][], opts: { numeric?: number[]; flag?: (r: any[]) => boolean } = {}) {
  const t = h("table");
  t.append(h("thead", {}, h("tr", {}, ...head.map((c, i) => h("th", { class: opts.numeric?.includes(i) ? "n" : undefined }, c)))));
  const tb = h("tbody");
  for (const r of rows) {
    const tr = h("tr", { class: opts.flag?.(r) ? "flag" : undefined });
    r.forEach((c, i) => tr.append(h("td", { class: opts.numeric?.includes(i) ? "n" : undefined, html: c === null ? "–" : String(c) })));
    tb.append(tr);
  }
  t.append(tb);
  return h("div", { class: "table-wrap" }, t);
}

export const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
