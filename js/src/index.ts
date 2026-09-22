// pravapis: bidirectional Belarusian orthography conversion (Narkamaŭka <-> Taraškievica).
//
// `convert()`'s return shape is the frozen cross-language contract (docs/API.md, §3.1
// of the plan this package implements): the same `{text, direction, engine_version,
// data_version, changes, unresolved}` the HTTP API returns, so a caller can swap
// between the two with no code change beyond how the call is made.
//
// This entry point does not include data/lexicon/proper_nouns.tsv (one of the largest
// lexicon tables): import "pravapis/names" for a converter with it merged in.

import core from "./generated/core.json" with { type: "json" };
import { Converter } from "./pipeline.js";
import { conversionResultToDict, type Orthography } from "./types.js";
import type { CoreData } from "../scripts/lib/types.js";
import { ENGINE_VERSION } from "./version.js";

export { ENGINE_VERSION };
export const DATA_VERSION: string = (core as CoreData).dataVersion;

let cached: Converter | null = null;
function defaultConverter(): Converter {
  cached ??= Converter.fromCore(core as CoreData);
  return cached;
}

export interface ConvertOptions {
  from?: Orthography;
  to: Orthography;
}

function resolveDirection(options: ConvertOptions): Orthography {
  if (!options || typeof options.to !== "string") {
    throw new Error("convert() needs a 'to' orthography in its options");
  }
  if (options.to !== "narkamauka" && options.to !== "taraskievica") {
    throw new Error(`unknown orthography ${JSON.stringify(options.to)}; expected 'narkamauka' or 'taraskievica'`);
  }
  if (options.from !== undefined) {
    if (options.from !== "narkamauka" && options.from !== "taraskievica") {
      throw new Error(`unknown orthography ${JSON.stringify(options.from)}; expected 'narkamauka' or 'taraskievica'`);
    }
    if (options.from === options.to) {
      throw new Error(`'from' and 'to' are both ${options.to}; there is nothing to convert`);
    }
  }
  return options.to;
}

/**
 * Convert `text` between the two orthographies.
 *
 *     convert("снег", { to: "taraskievica" })
 *     // => { text: "сьнег", direction: "n2t", engine_version: "0.1.0",
 *     //      data_version: "1.3.0",
 *     //      changes: [{ start: 0, end: 5, from: "снег", to: "сьнег",
 *     //                  stage: "rule", rule: "palat.assim",
 *     //                  citation: "Збор 2005, §29", context: null }],
 *     //      unresolved: [] }
 *
 * Pass `unresolved: true` to populate `unresolved` (see the `unresolved` field on the
 * response, and docs/API.md — it costs a full extra scan, off by default).
 */
export function convert(
  text: string,
  options: ConvertOptions,
  opts: { unresolved?: boolean } = {}
): ReturnType<typeof conversionResultToDict> {
  const direction = resolveDirection(options);
  const result = defaultConverter().convert(text, direction, opts.unresolved ?? false);
  return conversionResultToDict(result, ENGINE_VERSION, DATA_VERSION);
}

/** A per-word trace of how `convert` reached its answer: the intermediate forms a
 * word passed through, alongside the same decision `convert` already made. */
export function explain(text: string, options: ConvertOptions): ReturnType<Converter["explain"]> {
  const direction = resolveDirection(options);
  return defaultConverter().explain(text, direction);
}

export type { Orthography, Method, ConversionResult, Conversion, TokenExplanation } from "./types.js";
export { Converter } from "./pipeline.js";
