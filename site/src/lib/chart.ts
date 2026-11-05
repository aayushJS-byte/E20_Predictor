import * as d3 from "d3";
import { tip } from "./ui";

export interface Frame {
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>;
  g: d3.Selection<SVGGElement, unknown, null, undefined>;
  w: number;
  h: number;
  x: any;
  y: d3.ScaleLinear<number, number>;
  layer: (cls?: string) => d3.Selection<SVGGElement, unknown, null, undefined>;
  redrawAxes: () => void;
}

export interface FrameOpts {
  width?: number;
  height?: number;
  margin?: { top: number; right: number; bottom: number; left: number };
  x: any;
  y: [number, number];
  xLabel?: string;
  yLabel?: string;
  xTicks?: number;
  yTicks?: number;
  xFormat?: (d: any) => string;
  yFormat?: (d: any) => string;
  reverseX?: boolean;
}

export function frame(container: HTMLElement, o: FrameOpts): Frame {
  const W = o.width ?? 720, H = o.height ?? 300;
  const m0 = o.margin ?? { top: 12, right: 24, bottom: 40, left: 56 };
  const m = o.yLabel ? { ...m0, top: m0.top + 16 } : m0; // room for the y label above the top tick
  const w = W - m.left - m.right, h = H - m.top - m.bottom;
  const svg = d3.select(container).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img");
  const g = svg.append("g").attr("transform", `translate(${m.left},${m.top})`);
  const x = o.x.range(o.reverseX ? [w, 0] : [0, w]);
  const y = d3.scaleLinear().domain(o.y).range([h, 0]);
  const gridG = g.append("g").attr("class", "grid");
  const xa = g.append("g").attr("class", "axis").attr("transform", `translate(0,${h})`);
  const ya = g.append("g").attr("class", "axis");
  const redrawAxes = () => {
    gridG.call(d3.axisLeft(y).ticks(o.yTicks ?? 5).tickSize(-w).tickFormat(() => "") as any);
    xa.call(d3.axisBottom(x).ticks(o.xTicks ?? 6).tickSize(4).tickPadding(6).tickFormat(o.xFormat ?? (null as any)) as any);
    ya.call(d3.axisLeft(y).ticks(o.yTicks ?? 5).tickSize(0).tickPadding(8).tickFormat(o.yFormat ?? (null as any)) as any);
  };
  redrawAxes();
  if (o.xLabel) g.append("text").attr("class", "axis-label").attr("x", w).attr("y", h + 32).attr("text-anchor", "end").text(o.xLabel);
  if (o.yLabel) g.append("text").attr("class", "axis-label").attr("x", -m.left + 4).attr("y", -14).attr("text-anchor", "start").text(o.yLabel);
  const layer = (cls = "") => g.append("g").attr("class", cls);
  return { svg, g, w, h, x, y, layer, redrawAxes };
}

export interface HoverSeries {
  label: string;
  color: string;
  xs: ArrayLike<number> | number[];
  ys: ArrayLike<number> | number[];
  fmt?: (v: number) => string;
}

/** Crosshair + tooltip over line series sharing an x axis (nearest x). */
export function crosshair(f: Frame, series: () => HoverSeries[], xFmt: (x: number) => string, onMove?: (x: number | null) => void) {
  const rule = f.g.append("line").attr("y1", 0).attr("y2", f.h).style("stroke", "var(--muted)").style("stroke-width", 1).style("opacity", 0);
  const dots = f.g.append("g");
  f.g
    .append("rect")
    .attr("width", f.w)
    .attr("height", f.h)
    .style("fill", "transparent")
    .on("pointermove", (ev: PointerEvent) => {
      const [px] = d3.pointer(ev);
      const xv = f.x.invert(px) as number;
      const ss = series();
      if (!ss.length) return;
      const rows: string[] = [];
      dots.selectAll("*").remove();
      let xr = xv;
      for (const s of ss) {
        const xs = Array.from(s.xs as ArrayLike<number>);
        if (!xs.length) continue;
        const i = Math.max(0, Math.min(xs.length - 1, d3.bisectCenter(xs, xv)));
        xr = xs[i];
        const yv = (s.ys as ArrayLike<number>)[i];
        if (!Number.isFinite(yv)) continue;
        dots.append("circle").attr("cx", f.x(xs[i])).attr("cy", f.y(yv)).attr("r", 4)
          .style("fill", s.color).style("stroke", "var(--surface)").style("stroke-width", 2);
        rows.push(`<div><span class="sw" style="background:${s.color}"></span><span class="k">${s.label}</span> <b>${s.fmt ? s.fmt(yv) : yv.toFixed(3)}</b></div>`);
      }
      rule.attr("x1", f.x(xr)).attr("x2", f.x(xr)).style("opacity", 0.6);
      tip(`<div class="k">${xFmt(xr)}</div>${rows.join("")}`, ev);
      onMove?.(xr);
    })
    .on("pointerleave", () => {
      rule.style("opacity", 0);
      dots.selectAll("*").remove();
      tip(null);
      onMove?.(null);
    });
}

export function linePath(xs: ArrayLike<number>, ys: ArrayLike<number>, f: Frame) {
  const pts: [number, number][] = [];
  for (let i = 0; i < xs.length; i++) if (Number.isFinite(ys[i])) pts.push([f.x(xs[i]), f.y(ys[i])]);
  return d3.line()(pts) ?? "";
}
