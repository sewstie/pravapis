// Loanword adaptation rules (Narkamaŭka <-> Taraškievica). Mirrors
// src/pravapis/rules/loanwords.py. Each function is a pure string transducer over a
// span (see StemMatch), composed by the rule engine — never by each other, except
// deriveTargetEntries, which composes them once at startup to build the reverse
// (Taraškievica-keyed) etymology index the same way pravapis.pipeline.Converter does.

import { markAssimilativeSoftness } from "./palatalization.js";
import type { Alternation, StemMatch, StemRow, WordClass } from "../lexicon/stem-index.js";
import { spansStill, allows } from "../lexicon/stem-index.js";

const SOFT_L_VOWEL: Readonly<Record<string, string>> = { а: "я", о: "ё", у: "ю" };
const ALREADY_SOFT = new Set(["е", "ё", "і", "ю", "я"]);
const Y_TRIGGERS = new Set(["д", "т", "з", "с", "ц", "ж", "ш", "ч", "р"]);
const E_BLOCKERS = new Set(["л", "г", "ґ", "к", "х"]);
const CONSONANTS = new Set([
  "б", "в", "г", "ґ", "д", "ж", "з", "й", "к", "л", "м", "н", "п", "р", "с", "т", "ў", "ф",
  "х", "ц", "ч", "ш",
]);
const EJSK_RE = /ейск/g;
const F_NAMES: Readonly<Record<string, string>> = { фёдар: "хведар", фядос: "хвядос" };
const F_RE = /^(?:фёдар|фядос)/;
const EU_RE = /^еў/;

function span(word: string, match: StemMatch): [string, string, string] | null {
  if (!spansStill(match, word)) return null;
  return [word.slice(0, match.start), word.slice(match.start, match.end), word.slice(match.end)];
}

/** ла -> ля, ло -> лё, лу -> лю, and л -> ль before a consonant or at the end.
 * `following` is the character after the stem in the word being converted — a
 * stem-final л is not word-final. */
export function palatalizeL(stem: string, following = ""): string {
  const out: string[] = [];
  for (let i = 0; i < stem.length; i++) {
    const ch = stem[i]!;
    if (ch !== "л") {
      out.push(ch);
      continue;
    }
    const nxt = i + 1 < stem.length ? stem[i + 1]! : (following[0] ?? "");
    if (ALREADY_SOFT.has(nxt) || nxt === "ь" || nxt in SOFT_L_VOWEL) {
      out.push(ch);
    } else {
      out.push("ль");
    }
  }
  const text = out.join("");
  return text.replace(/л([аоу])/g, (_m, v: string) => "л" + SOFT_L_VOWEL[v]);
}

export function applyLPalatalization(word: string, match: StemMatch): string {
  if (!allows(match, "l")) return word;
  const s = span(word, match);
  if (s === null) return word;
  const [before, stem, after] = s;
  return before + palatalizeL(stem, after) + after;
}

/** і -> ы after a hard dental or husher. */
export function iToY(stem: string): string {
  return [...stem]
    .map((ch, i) => (ch === "і" && i > 0 && Y_TRIGGERS.has(stem[i - 1]!) ? "ы" : ch))
    .join("");
}

export function applyIToY(word: string, match: StemMatch): string {
  if (!allows(match, "i")) return word;
  const s = span(word, match);
  if (s === null) return word;
  const [before, stem, after] = s;
  return before + iToY(stem) + after;
}

/** е -> э after any consonant except л and the velars г, ґ, к, х. The adjective suffix
 * -ейск- is exempt: its е is structural and never hardens. */
export function eToEh(stem: string): string {
  const protectedIdx = new Set<number>();
  for (const m of stem.matchAll(EJSK_RE)) protectedIdx.add(m.index!);
  return [...stem]
    .map((ch, i) => {
      if (ch !== "е" || i === 0 || protectedIdx.has(i)) return ch;
      const prev = stem[i - 1]!;
      return CONSONANTS.has(prev) && !E_BLOCKERS.has(prev) ? "э" : ch;
    })
    .join("");
}

export function applyEToEh(word: string, match: StemMatch): string {
  if (!allows(match, "e")) return word;
  const s = span(word, match);
  if (s === null) return word;
  const [before, stem, after] = s;
  return before + eToEh(stem) + after;
}

/** ґ -> г, always (Narkamaŭka has no ґ). */
export function removeGDistinction(word: string): string {
  return word.replaceAll("ґ", "г");
}

/** еўропа -> эўропа, еўрапейскі -> эўрапейскі. */
export function applyEuPrefix(word: string): string {
  return word.replace(EU_RE, "эў");
}

/** фёдар -> хведар, фядос -> хвядос, with endings kept (optional; §81 Заўвага Б). */
export function applyFSubstitution(word: string): string {
  if (word in F_NAMES) return F_NAMES[word]!;
  const m = F_RE.exec(word);
  if (m === null) return word;
  const stem = m[0];
  return (F_NAMES[stem] ?? stem) + word.slice(stem.length);
}

/** Replace the matched stem with its explicit target (the stems.tsv `target` column). */
export function applyStemTarget(word: string, match: StemMatch): string {
  if (match.target === null) return word;
  const s = span(word, match);
  if (s === null) return word;
  const [before, , after] = s;
  return before + match.target + after;
}

// --- deriving the Taraškievica side of the inventory --------------------------------
type Alternator = (stem: string) => string;
const FORWARD: ReadonlyArray<readonly [Alternation, Alternator]> = [
  ["g", (s) => s.replace("г", "ґ")],
  ["l", (s) => palatalizeL(s)],
  ["i", iToY],
  ["e", eToEh],
];

function applyAlternations(stem: string, alternations: readonly Alternation[], following = ""): string {
  const set = new Set(alternations);
  for (const [code, fn] of FORWARD) {
    if (!set.has(code)) continue;
    stem = code === "l" ? palatalizeL(stem, following) : fn(stem);
  }
  return stem;
}

function targetStem(entry: StemRow): string {
  return entry.target ?? applyAlternations(entry.stem, entry.alternations);
}

/** `entries` re-keyed by their Taraškievica form, for the T -> N direction. Every
 * reverse entry carries the Narkamaŭka stem as its `target`, so T -> N is a stem
 * substitution, never an inverse transducer.
 *
 * Deliberately does not filter on provenance here, mirroring pravapis.rules.loanwords
 * exactly: an "uncertain" entry (loan or native) still flows through and produces
 * derived variants, all inheriting its provenance — StemIndex's own applied-filter
 * (see ../lexicon/stem-index.ts) is what keeps them out of the usable index, the same
 * single place Python's StemIndex.__init__ does it. */
export function deriveTargetEntries(entries: readonly StemRow[]): StemRow[] {
  const out: StemRow[] = [];
  for (const e of entries) {
    if (e.class === "native") {
      out.push(e);
      continue;
    }
    if (e.forwardOnly.length > 0 || !(e.alternations.length > 0 || e.target !== null)) continue;

    const derived = targetStem(e);
    const softened =
      e.target === null ? markAssimilativeSoftness(e.stem) : markAssimilativeSoftness(e.target);
    const inWord = e.target === null ? applyAlternations(e.stem, e.alternations, "а") : derived;
    const variants = [
      derived,
      inWord,
      markAssimilativeSoftness(derived),
      markAssimilativeSoftness(inWord),
      e.target === null ? applyAlternations(softened, e.alternations) : softened,
    ];
    const seen = new Set<string>();
    for (const stem of variants) {
      if (seen.has(stem)) continue;
      seen.add(stem);
      out.push({
        stem,
        anchored: e.anchored,
        class: e.class,
        alternations: [],
        forwardOnly: [],
        source: e.source,
        provenance: e.provenance,
        target: e.stem,
      });
    }
  }
  return out;
}

export type { WordClass };
