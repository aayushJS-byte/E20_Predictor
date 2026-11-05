import * as d3 from "d3";
import { chapter } from "../lib/ui";

export function chain() {
  const { sec, inner } = chapter("chain", 2, "Four ways in", "Between the distillery and your car, water can enter at four points.", "The supply chain");
  const stages = ["Distillery", "Road tanker", "Depot", "Retail tank", "Vehicle"];
  const ingress = [
    { at: 1, t: ["Wet tanker", "residual water"] },
    { at: 2, t: ["Transfers", "no ethanol pipeline"] },
    { at: 2.78, t: ["Breathing", "humid air via vent"] },
    { at: 3.22, t: ["Bad seals", "rain via fill cap"] },
  ];
  const card = document.createElement("div");
  card.className = "card";
  const W = 1000, H = 300;
  const svg = d3.select(card).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", "Supply chain with four water ingress points");
  const x = (i: number) => 100 + i * 200;
  const yN = 100;
  svg.append("line").attr("x1", x(0)).attr("x2", x(4)).attr("y1", yN).attr("y2", yN).style("stroke", "var(--axis)").style("stroke-width", 2);
  stages.forEach((s, i) => {
    const g = svg.append("g").attr("transform", `translate(${x(i)},${yN})`);
    const key = i === 2 || i === 3;
    g.append("rect").attr("x", -72).attr("y", -24).attr("width", 144).attr("height", 48).attr("rx", 24)
      .style("fill", key ? "var(--ink)" : "var(--surface)").style("stroke", key ? "none" : "var(--axis)").style("stroke-width", 1.5);
    g.append("text").attr("text-anchor", "middle").attr("dy", 5).style("font-size", "14px").style("font-weight", 600).style("fill", key ? "var(--page)" : "var(--ink)").text(s);
  });
  const layer = (i: number, label: string, color: string) => {
    svg.append("text").attr("x", x(i)).attr("y", yN - 46).attr("text-anchor", "middle").style("font", "500 11px var(--mono)").style("letter-spacing", "0.06em").style("fill", color).text(label);
  };
  layer(2, "LAYER A", "var(--s1)");
  layer(3, "LAYER B · SOLUTION 4", "var(--s2)");
  ingress.forEach((g, k) => {
    const px = x(g.at), cyy = 196;
    svg.append("line").attr("x1", px).attr("x2", px).attr("y1", yN + 26).attr("y2", cyy - 16).style("stroke", "var(--water)").style("stroke-width", 1.5).style("stroke-dasharray", "3 4");
    svg.append("circle").attr("cx", px).attr("cy", cyy).attr("r", 15).style("fill", "var(--water)");
    svg.append("text").attr("x", px).attr("y", cyy + 5).attr("text-anchor", "middle").style("fill", "#fff").style("font-weight", 700).style("font-size", "13px").text(k + 1);
    svg.append("text").attr("x", px).attr("y", cyy + 40).attr("text-anchor", "middle").style("font-size", "14px").style("font-weight", 600).style("fill", "var(--ink)").text(g.t[0]);
    svg.append("text").attr("x", px).attr("y", cyy + 60).attr("text-anchor", "middle").style("font-size", "12px").text(g.t[1]);
  });
  inner.append(card);
  return sec;
}
