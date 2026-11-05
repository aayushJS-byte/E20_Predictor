// The TypeScript tank simulator must reproduce sim/tank.py step by step.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { simulate, type TankParams } from "../src/lib/sim";

const root = resolve(__dirname, "../..");
const fx = JSON.parse(readFileSync(resolve(root, "tests/fixtures/sim_reference.json"), "utf8"));
const constants = JSON.parse(readFileSync(resolve(root, "site/public/data/constants.json"), "utf8"));
const weather = { times: fx.times, ...fx.weather };

describe("TS simulator reproduces Python", () => {
  fx.cases.forEach((c: any, k: number) => {
    it(`case ${k} (${c.params.seal}, drain ${c.params.drain_out})`, () => {
      const out = simulate(weather, c.params as TankParams, constants);
      expect(out.events.map((e) => [e.step, e.type])).toEqual(c.events.map((e: any) => [e.step, e.type]));
      for (const key of Object.keys(c.trace)) {
        const py: (number | null)[] = c.trace[key];
        const ts = (out.trace as any)[key] as Float64Array;
        let worst = 0;
        py.forEach((v, i) => {
          if (v === null) return;
          worst = Math.max(worst, Math.abs(ts[i] - v) / Math.max(1, Math.abs(v)));
        });
        expect(worst, key).toBeLessThan(1e-6);
      }
      expect(Math.abs(out.ledger.imbalance)).toBeLessThan(1e-6);
    });
  });
});
