// Builds js/src/generated/{core,names,translit,chars}.json from data/, for a
// TypeScript pravapis port.
//
//     npm run build-data          # from js/
//
// Reads data/MANIFEST only, in the order it lists — never a glob — because that file
// (src/pravapis/dataversion.py, "0.1") is the one place "the data" is enumerated, and
// this build's data hash has to be computed the exact same way the Python side
// computes it or the CI cross-check below is meaningless.
//
// For every listed file with a JSON Schema (data/schemas/*.schema.json — rules, stems,
// function words, translit), the parsed content is validated against that schema
// before anything is emitted: a file can be syntactically fine YAML/TSV and still not
// be a rule set, and a port should never ship data nobody checked. Files with no
// schema (the plain lexicon TSVs — loanwords, exceptions, proper nouns, case forms)
// are read and used unvalidated, exactly as pravapis.dataspec.validate_data() leaves
// them unvalidated on the Python side. The three committed marisa-trie files
// (morphology/ment_lemmas.marisa, stress/*.marisa) are hashed — their bytes are part of
// the data, so they are part of the hash — but not decoded: nothing here reads marisa's
// binary trie format, and nothing in core/names/translit.json needs to yet. Whatever
// consumes stress-conditioned jakanne in a JS port will need that separately.
//
// Named-group and replacement-token translation ((?P<name>...) -> (?<name>...), \1 /
// \g<name> -> $1 / $<name>) happens here, mechanically, in ./lib/regex-translate.ts —
// the YAML source stays single-dialect (Python's `regex` module syntax, the dialect
// rules.schema.json declares as normative). Everything else in a pattern is already
// JS-compatible by construction: scripts/lint_patterns.py, at the repo root, compiles
// every data/rules/ pattern with both Python's stdlib `re` and Node's
// `new RegExp(p, 'u')` and rejects the handful of constructs that would compile but
// silently misbehave (\w \W \b \B \Z, inline flags, conditional groups). This build
// goes one step further for the translated result: it re-applies every rule's own
// inline test cases through the translated JS pattern + replacement and fails if the
// answer differs, so a translation bug shows up here rather than in a port's own tests.

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { computeDataHash, readDataVersion, readManifest } from "./lib/manifest.js";
import { loadSchema as loadSchemaFile, type Problem } from "./lib/schema.js";
import { readRulesFile } from "./lib/rules.js";
import { readStemsFile } from "./lib/stems.js";
import { readFunctionWordsFile } from "./lib/function-words.js";
import { readPairsFile, readCaseFormsFile } from "./lib/lexicon.js";
import { readTranslitFile } from "./lib/translit.js";
import { readAlphabetFile, readApostrophesFile, readHomoglyphsFile } from "./lib/chars.js";
import { makeSanitizer } from "./lib/sanitize.js";
import { readMarisaTrieKeys } from "./lib/marisa-bridge.js";
import type {
  AlphabetData,
  ApostrophesData,
  CharsData,
  CoreData,
  DirectedPairs,
  HomoglyphsData,
  NamesData,
  RuleJson,
  StemRow,
  TranslitData,
  TranslitScheme,
} from "./lib/types.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const JS_ROOT = path.resolve(HERE, "..");
const REPO_ROOT = path.resolve(JS_ROOT, "..");
const DATA_DIR = path.join(REPO_ROOT, "data");
const SCHEMA_DIR = path.join(DATA_DIR, "schemas");
const OUT_DIR = path.join(JS_ROOT, "src", "generated");

const loadSchema = (name: string) => loadSchemaFile(SCHEMA_DIR, name);

function isBinary(relPath: string): boolean {
  return relPath.endsWith(".marisa");
}

async function main(): Promise<number> {
  const entries = await readManifest(DATA_DIR);
  const dataVersion = await readDataVersion(DATA_DIR);
  const dataHash = await computeDataHash(entries);

  const problems: Problem[] = [];
  const rules: RuleJson[] = [];
  let stems: StemRow[] = [];
  let loanwords: DirectedPairs = { n2t: {}, t2n: {} };
  let exceptions: DirectedPairs = { n2t: {}, t2n: {} };
  let properNouns: DirectedPairs = { n2t: {}, t2n: {} };
  let caseForms: Record<string, { genitive: string; dativeLocative: string }> = {};
  let functionWords: CoreData["functionWords"] = [];
  let mentLemmas: string[] = [];
  const translitSchemes: Record<string, TranslitScheme> = {};

  // Pass 1: the chars/*.tsv tables, needed to build a sanitize() before anything else
  // in pass 2 can use one. data/MANIFEST lists them first for exactly this reason, but
  // reading them in their own pass — rather than relying on loop order plus a null
  // check on every later branch — makes that dependency a fact about this function,
  // not a fact a reader has to notice about data/MANIFEST's ordering.
  let alphabet: AlphabetData | null = null;
  let apostrophes: ApostrophesData | null = null;
  let homoglyphs: HomoglyphsData | null = null;
  for (const entry of entries) {
    const rel = entry.relPath.replaceAll("\\", "/");
    if (rel === "chars/alphabet.tsv") {
      const raw = await readFile(entry.absPath, "utf-8");
      const { data, problems: fileProblems } = await readAlphabetFile(rel, raw, loadSchema);
      alphabet = data;
      problems.push(...fileProblems);
    } else if (rel === "chars/apostrophes.tsv") {
      const raw = await readFile(entry.absPath, "utf-8");
      const { data, problems: fileProblems } = await readApostrophesFile(rel, raw, loadSchema);
      apostrophes = data;
      problems.push(...fileProblems);
    } else if (rel === "chars/homoglyphs.tsv") {
      const raw = await readFile(entry.absPath, "utf-8");
      const { data, problems: fileProblems } = await readHomoglyphsFile(rel, raw, loadSchema);
      homoglyphs = data;
      problems.push(...fileProblems);
    }
  }
  if (!alphabet || !apostrophes || !homoglyphs) {
    throw new Error("data/MANIFEST is missing one of chars/{alphabet,apostrophes,homoglyphs}.tsv");
  }
  const sanitize = makeSanitizer(homoglyphs, apostrophes);

  // Pass 2: everything else.
  for (const entry of entries) {
    const rel = entry.relPath.replaceAll("\\", "/");
    if (rel.startsWith("chars/")) continue; // pass 1
    if (rel === "morphology/ment_lemmas.marisa") {
      mentLemmas = readMarisaTrieKeys(entry.absPath);
      continue;
    }
    if (isBinary(rel)) continue; // stress/*.marisa: hashed only, not decoded — see marisa-bridge.ts

    const raw = await readFile(entry.absPath, "utf-8");

    if (rel.startsWith("rules/")) {
      const { rules: fileRules, problems: fileProblems } = await readRulesFile(rel, raw, loadSchema);
      rules.push(...fileRules);
      problems.push(...fileProblems);
    } else if (rel === "lexicon/stems/stems.tsv") {
      const { rows, problems: fileProblems } = await readStemsFile(
        rel,
        raw,
        SCHEMA_DIR,
        loadSchema,
        sanitize
      );
      stems = rows;
      problems.push(...fileProblems);
    } else if (rel === "lexicon/loanwords.tsv") {
      const { pairs, problems: fileProblems } = readPairsFile(rel, raw, sanitize);
      loanwords = pairs;
      problems.push(...fileProblems);
    } else if (rel === "lexicon/exceptions.tsv") {
      const { pairs, problems: fileProblems } = readPairsFile(rel, raw, sanitize);
      exceptions = pairs;
      problems.push(...fileProblems);
    } else if (rel === "lexicon/proper_nouns.tsv") {
      const { pairs, problems: fileProblems } = readPairsFile(rel, raw, sanitize);
      properNouns = pairs;
      problems.push(...fileProblems);
    } else if (rel === "lexicon/case/ambiguous.tsv") {
      const { rows, problems: fileProblems } = readCaseFormsFile(rel, raw, sanitize);
      caseForms = rows;
      problems.push(...fileProblems);
    } else if (rel === "morphology/function_words.tsv") {
      const { rows, problems: fileProblems } = await readFunctionWordsFile(rel, raw, loadSchema);
      functionWords = rows;
      problems.push(...fileProblems);
    } else if (rel.startsWith("translit/")) {
      const { scheme, problems: fileProblems } = await readTranslitFile(rel, raw, loadSchema);
      if (scheme) translitSchemes[scheme.scheme] = scheme;
      problems.push(...fileProblems);
    } else {
      throw new Error(
        `${rel}: data/MANIFEST lists this file but build-data.ts has no reader for it — ` +
          "add one, or confirm it only needs to be hashed and add it to isBinary()'s skip list"
      );
    }
  }

  if (problems.length > 0) {
    console.error(`${problems.length} problem(s):`);
    for (const p of problems) console.error(`  ${p.file} :: ${p.where} :: ${p.message}`);
    return 1;
  }

  const core: CoreData = {
    schema: "tag:pravapis,2026:schema:js-core:1",
    dataVersion,
    dataHash,
    rules,
    stems,
    loanwords,
    exceptions,
    caseForms,
    functionWords,
    mentLemmas,
  };
  const names: NamesData = {
    schema: "tag:pravapis,2026:schema:js-names:1",
    dataVersion,
    dataHash,
    properNouns,
  };
  const translit: TranslitData = {
    schema: "tag:pravapis,2026:schema:js-translit:1",
    dataVersion,
    dataHash,
    schemes: translitSchemes,
  };
  const chars: CharsData = {
    schema: "tag:pravapis,2026:schema:js-chars:1",
    dataVersion,
    dataHash,
    alphabet,
    apostrophes,
    homoglyphs,
  };

  await mkdir(OUT_DIR, { recursive: true });
  await writeFile(path.join(OUT_DIR, "core.json"), JSON.stringify(core, null, 2) + "\n");
  await writeFile(path.join(OUT_DIR, "names.json"), JSON.stringify(names, null, 2) + "\n");
  await writeFile(path.join(OUT_DIR, "translit.json"), JSON.stringify(translit, null, 2) + "\n");
  await writeFile(path.join(OUT_DIR, "chars.json"), JSON.stringify(chars, null, 2) + "\n");

  console.log(`wrote ${path.relative(REPO_ROOT, OUT_DIR)}/{core,names,translit,chars}.json`);
  console.log(`data version: ${dataVersion}`);
  console.log(`data hash:    ${dataHash}`);
  return 0;
}

main().then(
  (code) => process.exit(code),
  (exc) => {
    console.error(exc instanceof Error ? exc.stack ?? exc.message : String(exc));
    process.exit(1);
  }
);
