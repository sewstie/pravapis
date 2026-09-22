// Longest-match lookup over the etymology stem inventory (data/lexicon/stems/stems.tsv,
// exported as `stems` in generated/core.json) — the JS-side equivalent of
// pravapis.lexicon.stems.StemIndex.
//
// The Python side backs anchored stems with a marisa_trie.Trie so a lookup stays
// O(len(word)) as the inventory grows into the thousands (see StemIndex's own
// docstring). That trade only pays for itself past a few hundred entries; at the
// current scale (177 anchored, 8 unanchored — see data/lexicon/stems/stems.tsv) a
// sorted array plus binary search is simpler, has no dependency, and is not
// measurably slower. Revisit only if names.json (the larger of the two lexicon
// tables) gzips past ~200KB; that is the signal this scale assumption stopped
// holding, not a hardcoded stem count.

// StemRow/Alternation describe core.json's `stems` array shape (data/schemas/
// stems.schema.json is the normative source). Imported as types only from the build
// script's type module: a `import type` is fully erased at compile time, so this adds
// no runtime dependency from the shipped port onto build tooling — just one shared
// definition instead of a copy that can silently drift from it.
import type { Alternation, StemRow } from "../../scripts/lib/types.js";
export type { Alternation, StemRow };
export type WordClass = StemRow["class"];

/** Where a known stem was found in a word, and what it licenses. Mirrors
 * pravapis.lexicon.stems.StemMatch. */
export interface StemMatch {
  stem: string;
  cls: WordClass;
  alternations: readonly Alternation[];
  start: number;
  end: number;
  target: string | null;
  /** Length of the word this match was resolved against, or -1 for an anchored match
   * (which is always resolved at [0, stem.length) and so never goes stale). A rule
   * that changes the word's length after resolution invalidates a nonnegative one —
   * see spansStill(). */
  wordLen: number;
}

/** Applied loan stems only: a stem with `provenance: "uncertain"`, or a native stem,
 * is parsed and counted but never licenses a rewrite. Mirrors StemEntry.applied. */
const APPLIED: ReadonlySet<StemRow["provenance"]> = new Set(["cited", "reviewed", "derived"]);

function isApplied(row: StemRow): boolean {
  return APPLIED.has(row.provenance);
}

function toMatch(row: StemRow, start: number, end: number, wordLen: number): StemMatch {
  return {
    stem: row.stem,
    cls: row.class,
    alternations: row.alternations,
    start,
    end,
    target: row.target,
    wordLen,
  };
}

/** Are `match.start`/`match.end` still pointing at the right letters of `word`? False
 * after a rule has changed `word`'s length since the match was resolved. */
export function spansStill(match: StemMatch, word: string): boolean {
  return match.wordLen < 0 || word.length === match.wordLen;
}

/** Does this match license `alternation`? Only a loan stem licenses anything — a
 * native stem's whole point is that it claims nothing about the codification. */
export function allows(match: StemMatch, alternation: Alternation): boolean {
  return match.cls === "loan" && match.alternations.includes(alternation);
}

export class StemIndex {
  private readonly anchoredSorted: string[];
  private readonly byAnchoredStem: Map<string, StemRow>;
  private readonly maxAnchoredLen: number;
  /** Longest first, so the leftmost-position scan in `match()` prefers the longest
   * stem among several that start at the same position — the same preference
   * `regex.compile("|".join(...))`'s ordered alternation gives the Python side. */
  private readonly unanchoredByLenDesc: StemRow[];

  constructor(rows: readonly StemRow[]) {
    const applied = rows.filter(isApplied);
    const anchored = applied.filter((r) => r.anchored);
    const unanchored = applied.filter((r) => !r.anchored);

    this.anchoredSorted = anchored.map((r) => r.stem).sort();
    this.byAnchoredStem = new Map(anchored.map((r) => [r.stem, r]));
    this.maxAnchoredLen = anchored.reduce((max, r) => Math.max(max, r.stem.length), 0);
    this.unanchoredByLenDesc = unanchored.sort((a, b) => b.stem.length - a.stem.length);
  }

  static empty(): StemIndex {
    return new StemIndex([]);
  }

  get size(): number {
    return this.byAnchoredStem.size + this.unanchoredByLenDesc.length;
  }

  /** Exact membership in the sorted anchored-stem array, by binary search. */
  private hasAnchored(candidate: string): boolean {
    let lo = 0;
    let hi = this.anchoredSorted.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const value = this.anchoredSorted[mid]!;
      if (value === candidate) return true;
      if (value < candidate) lo = mid + 1;
      else hi = mid - 1;
    }
    return false;
  }

  /** The longest anchored stem that prefixes `w`, tried longest-first so the first
   * hit is already the answer — no need to scan the rest. One binary search per
   * candidate length, capped at the longest stem in the inventory: at most
   * `maxAnchoredLen` searches of a ~200-entry array, not a measurable cost. */
  private matchAnchored(w: string): StemMatch | null {
    const maxLen = Math.min(this.maxAnchoredLen, w.length);
    for (let len = maxLen; len >= 1; len--) {
      const candidate = w.slice(0, len);
      if (this.hasAnchored(candidate)) {
        return toMatch(this.byAnchoredStem.get(candidate)!, 0, len, -1);
      }
    }
    return null;
  }

  /** The leftmost position in `w` where any unanchored stem occurs, preferring the
   * longest stem at that position — mirrors `regex.Pattern.search` over an
   * alternation of literals ordered longest-first. Only 8 unanchored stems exist
   * today (see data/lexicon/stems/stems.tsv), so a plain nested scan costs nothing;
   * this is not the array a bigger inventory would want. */
  private matchUnanchored(w: string): StemMatch | null {
    for (let i = 0; i < w.length; i++) {
      for (const row of this.unanchoredByLenDesc) {
        if (w.startsWith(row.stem, i)) {
          return toMatch(row, i, i + row.stem.length, w.length);
        }
      }
    }
    return null;
  }

  /** The longest known stem in `word`; anchored wins ties (an unanchored match only
   * overrides when it is strictly longer) — see data/schemas/stems.schema.json,
   * "Longest match wins... anchored beating unanchored on a tie". */
  match(word: string): StemMatch | null {
    const w = word.toLowerCase();
    const anchored = this.matchAnchored(w);
    const unanchored = this.matchUnanchored(w);
    if (!unanchored) return anchored;
    if (!anchored) return unanchored;
    const anchoredSpan = anchored.end - anchored.start;
    const unanchoredSpan = unanchored.end - unanchored.start;
    return unanchoredSpan > anchoredSpan ? unanchored : anchored;
  }
}
