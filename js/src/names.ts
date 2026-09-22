// pravapis/names — `convert`, but with data/lexicon/proper_nouns.tsv merged into the
// lexicon. A separate entry point (not part of "."), loaded lazily and only by a
// caller that needs it: most conversions never touch a proper noun, and the table is
// one of the largest lexicon files (see js/src/pipeline.ts's Converter.fromCore).

import core from "./generated/core.json" with { type: "json" };
import names from "./generated/names.json" with { type: "json" };
import { Converter } from "./pipeline.js";
import { conversionResultToDict, type Orthography } from "./types.js";
import type { CoreData, NamesData } from "../scripts/lib/types.js";
import { ENGINE_VERSION } from "./version.js";

export interface ConvertOptions {
  from?: Orthography;
  to: Orthography;
}

const DATA_VERSION: string = (core as CoreData).dataVersion;

let cached: Converter | null = null;
function converterWithNames(): Converter {
  cached ??= Converter.fromCore(core as CoreData, (names as NamesData).properNouns);
  return cached;
}

function resolveDirection(options: ConvertOptions): Orthography {
  if (!options || typeof options.to !== "string") {
    throw new Error("convert() needs a 'to' orthography in its options");
  }
  return options.to;
}

export function convert(
  text: string,
  options: ConvertOptions,
  opts: { unresolved?: boolean } = {}
): ReturnType<typeof conversionResultToDict> {
  const direction = resolveDirection(options);
  const result = converterWithNames().convert(text, direction, opts.unresolved ?? false);
  return conversionResultToDict(result, ENGINE_VERSION, DATA_VERSION);
}

export function explain(text: string, options: ConvertOptions): ReturnType<Converter["explain"]> {
  const direction = resolveDirection(options);
  return converterWithNames().explain(text, direction);
}
