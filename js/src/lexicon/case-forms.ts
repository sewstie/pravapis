// Lexical substitutions whose target depends on grammatical case (data/lexicon/case/
// ambiguous.tsv, e.g. Германіі -> Нямеччыны / Нямеччыне). Mirrors
// src/pravapis/lexicon/case_forms.py.

import type { CaseFormsRow } from "../../scripts/lib/types.js";

export const CASE_RULE_ID = "lex.case_context";

export class CaseForms {
  constructor(
    private readonly table: ReadonlyMap<string, CaseFormsRow>,
    private readonly dativeLocative: ReadonlySet<string> = new Set()
  ) {}

  static fromRecord(
    rows: Readonly<Record<string, CaseFormsRow>>,
    dativeLocative: ReadonlySet<string> = new Set()
  ): CaseForms {
    return new CaseForms(new Map(Object.entries(rows)), dativeLocative);
  }

  has(word: string): boolean {
    return this.table.has(word.toLowerCase());
  }

  /** [lowercase target, reason] for `word` after `previous`, or null if not listed. */
  choose(word: string, previous: string | null): [string, string] | null {
    const entry = this.table.get(word.toLowerCase());
    if (entry === undefined) return null;
    const prev = (previous ?? "").toLowerCase();
    if (this.dativeLocative.has(prev)) {
      return [entry.dativeLocative, `after «${prev}»: dative/locative`];
    }
    return [entry.genitive, "genitive (default: no dative/locative preposition before it)"];
  }
}
