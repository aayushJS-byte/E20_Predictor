import type { PlsModel } from "./pls";
import type { Constants } from "./sim";

const base = import.meta.env.BASE_URL;
const get = async <T>(p: string): Promise<T> => {
  const r = await fetch(`${base}data/${p}`);
  if (!r.ok) throw new Error(`failed to load ${p}: ${r.status}`);
  return r.json() as Promise<T>;
};

export interface Sample { id: string; ethanol_ref: number | null; water_ref: number | null; spectrum: number[] }
export interface Spectra { data_label: string; source: string; wavenumbers: number[]; samples: Sample[] }

export interface Data {
  constants: Constants;
  sources: any;
  spectra: Spectra;
  models: { ethanol: PlsModel; water: PlsModel };
  resultsA: any;
  metricsB: any;
  twin: any;
  val: { tolerance: any; layerA: any; ftir: any; layerB: any | null };
}

export async function loadAll(): Promise<Data> {
  const [constants, sources, spectra, ethanol, water, resultsA, metricsB, twin] = await Promise.all([
    get<Constants>("constants.json"),
    get<any>("sources.json"),
    get<Spectra>("layer_a/test_spectra.json"),
    get<PlsModel>("layer_a/model_ethanol.json"),
    get<PlsModel>("layer_a/model_water.json"),
    get<any>("layer_a/results.json"),
    get<any>("layer_b/metrics.json"),
    get<any>("layer_b/twin.json"),
  ]);
  const [tolerance, layerAv, ftir, layerB] = await Promise.all([
    get<any>("validation/tolerance.json"), get<any>("validation/layer_a.json"), get<any>("validation/ftir.json"),
    get<any>("validation/layer_b.json").catch(() => null),
  ]);
  return { constants, sources, spectra, models: { ethanol, water }, resultsA, metricsB, twin, val: { tolerance, layerA: layerAv, ftir, layerB } };
}

export const val = (c: Constants, ...path: string[]) => {
  let node: any = c;
  for (const p of path) node = node[p];
  return node && typeof node === "object" && "value" in node ? node.value : node;
};
