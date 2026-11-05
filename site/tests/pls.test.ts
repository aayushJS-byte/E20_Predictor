// The in-browser PLS must reproduce the Python predictions (layer_a/export.py) to < 1e-6.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { predict, type PlsModel } from "../src/lib/pls";

const root = resolve(__dirname, "../..");
const fixture = JSON.parse(readFileSync(resolve(root, "tests/fixtures/pls_reference.json"), "utf8"));
const models: Record<string, PlsModel> = {
  ethanol: JSON.parse(readFileSync(resolve(root, "site/public/data/layer_a/model_ethanol.json"), "utf8")),
  water: JSON.parse(readFileSync(resolve(root, "site/public/data/layer_a/model_water.json"), "utf8")),
};

describe("PLS export reproduces Python", () => {
  for (const c of fixture.cases) {
    it(`${c.target} / ${c.kind} / ${c.id}`, () => {
      const p = predict(models[c.target], c.spectrum);
      const rel = (a: number, b: number) => Math.abs(a - b) / Math.max(1, Math.abs(b));
      expect(rel(p.prediction, c.pred)).toBeLessThan(1e-6);
      expect(rel(p.half, c.half)).toBeLessThan(1e-6);
      expect(rel(p.leverage, c.h)).toBeLessThan(1e-6);
      expect(rel(p.q, c.q)).toBeLessThan(1e-6);
    });
  }
});
