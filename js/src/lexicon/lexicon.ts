// Exact-match lexicon: exceptions.tsv, loanwords.tsv and proper_nouns.tsv, combined
// exactly the way pravapis.lexicon.builder.build_from_sources does — one merged table
// per direction, first occurrence wins, reading the files in alphabetical filename
// order (exceptions, loanwords, proper_nouns). Mirrors pravapis.lexicon.store.Lexicon.
//
// Each source file's `DirectedPairs` (see scripts/lib/lexicon.ts) is already
// first-wins *within* that file and already split by the row's one-way n2t/t2n flag,
// so chaining three per-file lookups in that fixed order is equivalent to Python's
// single global-first-wins trie — it does not need to be rebuilt into one object here.

import type { DirectedPairs } from "../../scripts/lib/types.js";
import { recase } from "../casing.js";
import type { Orthography } from "../types.js";

function sideFor(pairs: DirectedPairs, direction: Orthography): Record<string, string> {
  return direction === "taraskievica" ? pairs.n2t : pairs.t2n;
}

export class Lexicon {
  constructor(
    private readonly exceptions: DirectedPairs,
    private readonly loanwords: DirectedPairs,
    private readonly properNouns: DirectedPairs
  ) {}

  /** Exact-key lookup (keys are lowercase). `direction` is the target orthography. */
  lookup(word: string, direction: Orthography): string | null {
    return (
      sideFor(this.exceptions, direction)[word] ??
      sideFor(this.loanwords, direction)[word] ??
      sideFor(this.properNouns, direction)[word] ??
      null
    );
  }

  lookupCi(word: string, direction: Orthography): string | null {
    const hit = this.lookup(word.toLowerCase(), direction);
    return hit === null ? null : recase(word, hit);
  }

  /** Is `word` explicitly listed as spelled the same in both orthographies? */
  isIdentity(word: string): boolean {
    const w = word.toLowerCase();
    return this.lookup(w, "taraskievica") === w || this.lookup(w, "narkamauka") === w;
  }
}
