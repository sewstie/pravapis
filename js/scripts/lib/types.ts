// Shapes shared between the build script and its output. `rules.schema.json` and
// `translit.schema.json` (data/schemas/) are NORMATIVE — these types describe exactly
// what those schemas describe, after the mechanical steps a static build can do once
// (direction aliases resolved, regex dialect translated) so the runtime engine doesn't
// have to redo them on every load.

export type Direction = "narkamauka_to_taraskievica" | "taraskievica_to_narkamauka";

export type Alternation = "l" | "i" | "e" | "g" | "eu";

export interface RuleTestCase {
  input: string;
  expected: string;
}

export interface RuleJson {
  id: string;
  description: string;
  citation: string;
  direction: Direction;
  /** JS RegExp source, already translated from the Python dialect. Absent for a
   * function-based rule. */
  pattern?: string;
  /** JS replacement template ($1, $<name>, $$ for a literal $). Only with `pattern`. */
  replacement?: string;
  /** 'module:callable' — unimplemented here. A port must supply this behaviour by
   * hand; see rules.schema.json. */
  function?: string;
  priority: number;
  repeat: boolean;
  optional: boolean;
  requires: string[];
  exceptions: string[];
  requiresClass?: "loan" | "native";
  alternation?: Alternation;
  tests: { positive: RuleTestCase[]; negative: RuleTestCase[] };
}

export interface StemRow {
  stem: string;
  anchored: boolean;
  class: "loan" | "native";
  alternations: Alternation[];
  forwardOnly: Alternation[];
  source: string;
  provenance: "cited" | "reviewed" | "derived" | "uncertain";
  target: string | null;
}

export interface FunctionWordRow {
  form: string;
  role:
    | "particle_n2t"
    | "particle_t2n"
    | "softening_preposition"
    | "clitic"
    | "stressed_initial_u"
    | "dative_locative_preposition";
  target: string | null;
  citation: string;
}

export interface CaseFormsRow {
  genitive: string;
  dativeLocative: string;
}

/** One lexicon TSV, indexed both ways. `n2t`/`t2n` are independent maps (not
 * inverses of each other): a row's optional third column can restrict it to one
 * direction, so a key present in `n2t` need not be present in `t2n` at all, and
 * `t2n`'s keys are the file's taraskievica column, not `n2t`'s values reversed. */
export interface DirectedPairs {
  n2t: Record<string, string>;
  t2n: Record<string, string>;
}

export interface StressData {
  /** Sorted blocks of front-coded words; see scripts/lib/stress.ts. */
  common: string[];
  proper: string[];
}

export interface CoreData {
  schema: "tag:pravapis,2026:schema:js-core:1";
  dataVersion: string;
  dataHash: string;
  rules: RuleJson[];
  stems: StemRow[];
  /** data/lexicon/loanwords.tsv. */
  loanwords: DirectedPairs;
  /** data/lexicon/exceptions.tsv. */
  exceptions: DirectedPairs;
  /** narkamauka -> {genitive, dativeLocative} (data/lexicon/case/ambiguous.tsv). */
  caseForms: Record<string, CaseFormsRow>;
  functionWords: FunctionWordRow[];
  /** Lemmas of the -мент/-мэнт alternation, decoded at build time. */
  mentLemmas: string[];
  /** Optional for callers constructing older core data; generated builds include it. */
  stress?: StressData;
}

export interface NamesData {
  schema: "tag:pravapis,2026:schema:js-names:1";
  dataVersion: string;
  dataHash: string;
  /** data/lexicon/proper_nouns.tsv. Kept out of core.json so a bundler can
   * code-split it: most conversions never touch a proper noun, and the table is one
   * of the largest lexicon files. */
  properNouns: DirectedPairs;
}

export interface TranslitCondition {
  when: string;
}

export interface TranslitMapping {
  from: string;
  to: string;
  when: string;
  lossy: boolean;
}

export interface TranslitScheme {
  scheme: string;
  description: string;
  source: string;
  reverseOf?: string;
  mappings: TranslitMapping[];
  tests: RuleTestCase[];
}

export interface TranslitData {
  schema: "tag:pravapis,2026:schema:js-translit:1";
  dataVersion: string;
  dataHash: string;
  schemes: Record<string, TranslitScheme>;
}

export interface AlphabetData {
  /** One entry per Belarusian letter. Also this project's case-fold table: fold a
   * letter by looking it up here, never with `String.toLowerCase()`/`toUpperCase()`
   * directly — see data/schemas/alphabet.schema.json. */
  pairs: { lower: string; upper: string }[];
}

export interface ApostrophesData {
  /** What every char in `chars` folds to (U+2019). */
  canonical: string;
  /** Every apostrophe-like character this project recognises, canonical included —
   * also the tokenizer's word-joining class for "з'ява". */
  chars: string[];
}

export interface HomoglyphsData {
  /** Latin/Cyrillic look-alike pairs. Read forward (latin -> cyrillic) for Cyrillic
   * input; read backwards (cyrillic -> latin) for Łacinka input. */
  pairs: { latin: string; cyrillic: string }[];
}

export interface CharsData {
  schema: "tag:pravapis,2026:schema:js-chars:1";
  dataVersion: string;
  dataHash: string;
  alphabet: AlphabetData;
  apostrophes: ApostrophesData;
  homoglyphs: HomoglyphsData;
}
