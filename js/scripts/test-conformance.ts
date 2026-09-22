// Replays conformance/cases.jsonl — the cross-language contract — against this port,
// the same way tests/test_conformance.py::test_every_case_passes_when_replayed does
// against the Python reference. A port is correct iff it passes this file.
//
//     npm test          # from js/

import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { Converter } from "../src/pipeline.js";
import { RuleEngine } from "../src/rules/engine.js";
import { StemIndex } from "../src/lexicon/stem-index.js";
import { deriveTargetEntries } from "../src/rules/loanwords.js";
import { Transliterator, type TransliterationResult } from "../src/translit/index.js";
import type { Orthography } from "../src/types.js";
import type { CoreData, DirectedPairs, RuleJson, TranslitData } from "../scripts/lib/types.js";

/** The corpus spells direction the long way ("narkamauka_to_taraskievica" — the
 * orthography the case *produces*), not the HTTP API's n2t/t2n wire code. */
function directionOf(long: string): Orthography {
  return long === "narkamauka_to_taraskievica" ? "taraskievica" : "narkamauka";
}

const HERE = path.dirname(fileURLToPath(import.meta.url));
const JS_ROOT = path.resolve(HERE, "..");
const REPO_ROOT = path.resolve(JS_ROOT, "..");
const CORPUS_FILE = path.join(REPO_ROOT, "conformance", "cases.jsonl");

interface Case {
  id: string;
  kind: string;
  direction: string | null;
  script: string;
  rule?: string;
  in: string;
  out: string;
  spans?: [number, number, string, string][];
  unresolved?: string[];
}

async function loadJson<T>(p: string): Promise<T> {
  return JSON.parse(await readFile(p, "utf-8")) as T;
}

async function main(): Promise<number> {
  const core = await loadJson<CoreData>(path.join(JS_ROOT, "src", "generated", "core.json"));
  const names = await loadJson<{ properNouns: DirectedPairs }>(
    path.join(JS_ROOT, "src", "generated", "names.json")
  );
  const translit = await loadJson<TranslitData>(path.join(JS_ROOT, "src", "generated", "translit.json"));

  const converter = Converter.fromCore(core, names.properNouns);

  // For `rule` cases: one rule alone, with etymology resolved from the same stem
  // inventory the pipeline uses — mirrors pravapis.conformance._single_rule_engine.
  const forwardStems = new StemIndex(core.stems);
  const reverseStems = new StemIndex(deriveTargetEntries(core.stems));
  const stemsByDirection = new Map<Orthography, StemIndex>([
    ["taraskievica", forwardStems],
    ["narkamauka", reverseStems],
  ]);
  const rulesById = new Map<string, RuleJson>(core.rules.map((r) => [r.id, r]));
  const schemesByName = new Map<string, Transliterator>();
  for (const name of Object.keys(translit.schemes)) {
    const script = name.replace(/_reverse$/, "") as "lacinka" | "official";
    schemesByName.set(name, Transliterator.fromData(translit, script, name.endsWith("_reverse")));
  }

  const raw = await readFile(CORPUS_FILE, "utf-8");
  const cases: Case[] = raw
    .split("\n")
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l) as Case);

  const failures: { id: string; message: string }[] = [];
  for (const c of cases) {
    if (c.kind === "rule") {
      const rule = rulesById.get(c.rule!);
      if (!rule) {
        failures.push({ id: c.id, message: `${c.id}: unknown rule ${c.rule}` });
        continue;
      }
      const engine = new RuleEngine([rule], stemsByDirection, true);
      const [got] = engine.apply(c.in, directionOf(c.direction!));
      if (got !== c.out) failures.push({ id: c.id, message: `${c.id}: ${JSON.stringify(c.in)} gave ${JSON.stringify(got)}, contract says ${JSON.stringify(c.out)}` });
    } else if (c.kind === "translit") {
      const scheme = schemesByName.get(c.script);
      if (!scheme) {
        failures.push({ id: c.id, message: `${c.id}: unknown scheme ${c.script}` });
        continue;
      }
      const got: TransliterationResult = scheme.transliterate(c.in);
      if (got.text !== c.out) failures.push({ id: c.id, message: `${c.id}: ${JSON.stringify(c.in)} gave ${JSON.stringify(got.text)}, contract says ${JSON.stringify(c.out)}` });
    } else if (c.kind === "unresolved") {
      const direction = directionOf(c.direction!);
      const result = converter.convert(c.in, direction, true);
      if (result.text !== c.out) {
        failures.push({ id: c.id, message: `${c.id}: ${JSON.stringify(c.in)} gave text ${JSON.stringify(result.text)}, contract says ${JSON.stringify(c.out)}` });
      }
      const want = c.unresolved ?? [];
      if (JSON.stringify(result.unresolved) !== JSON.stringify(want)) {
        failures.push({ id: c.id, message: `${c.id}: ${JSON.stringify(c.in)} gave unresolved=${JSON.stringify(result.unresolved)}, contract says ${JSON.stringify(want)}` });
      }
    } else {
      // gold | heldout | regression | offsets
      const direction = directionOf(c.direction!);
      const got = converter.convert(c.in, direction).text;
      if (got !== c.out) failures.push({ id: c.id, message: `${c.id}: ${JSON.stringify(c.in)} gave ${JSON.stringify(got)}, contract says ${JSON.stringify(c.out)}` });
    }
  }

  const knownGaps = await loadJson<{ reason: string; caseIds: string[] }>(
    path.join(HERE, "known-gaps.json")
  );
  const known = new Set(knownGaps.caseIds);
  const unexpected = failures.filter((f) => !known.has(f.id));
  const expectedButPassing = knownGaps.caseIds.filter((id) => !failures.some((f) => f.id === id));

  console.log(`${cases.length - failures.length}/${cases.length} conformance cases passed`);
  if (failures.length > 0) {
    console.log(`\n${failures.length} failure(s), ${failures.length - unexpected.length} of them known gaps:`);
    for (const f of failures) console.log(`  ${known.has(f.id) ? "(known gap) " : ""}${f.message}`);
  }

  let ok = true;
  if (unexpected.length > 0) {
    console.error(`\n${unexpected.length} UNEXPECTED failure(s) not in scripts/known-gaps.json:`);
    for (const f of unexpected) console.error(`  ${f.message}`);
    ok = false;
  }
  if (expectedButPassing.length > 0) {
    console.error(
      `\n${expectedButPassing.length} case(s) listed in scripts/known-gaps.json now PASS — ` +
        "remove them from that file:"
    );
    for (const id of expectedButPassing) console.error(`  ${id}`);
    ok = false;
  }
  if (ok && failures.length > 0) {
    console.log(`\nAll failures are known gaps (scripts/known-gaps.json): ${knownGaps.reason}`);
  }
  return ok ? 0 : 1;
}

main().then(
  (code) => process.exit(code),
  (exc) => {
    console.error(exc instanceof Error ? (exc.stack ?? exc.message) : String(exc));
    process.exit(1);
  }
);
