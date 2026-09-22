// A context-sensitive, longest-match transducer. Mirrors
// src/pravapis/translit/engine.py. Single left-to-right pass: at each position, the
// longest grapheme in the scheme's table whose context condition holds is emitted and
// consumed. Conditions read the SOURCE string only, never the output.

import { recase } from "../casing.js";
import type { TranslitScheme } from "../../scripts/lib/types.js";

const VOWELS = new Set(["а", "е", "ё", "і", "о", "у", "ы", "э", "ю", "я"]);
const GLIDES = new Set(["ў"]);
const SOFT_VOWELS = new Set(["е", "ё", "і", "ю", "я"]);
const APOSTROPHES = new Set(["’", "'", "ʼ", "`", "‘"]);
const SOFT_SIGN = "ь";

function isVowel(ch: string): boolean {
  return VOWELS.has(ch) || GLIDES.has(ch);
}

function isConsonant(ch: string): boolean {
  return !!ch && /\p{L}/u.test(ch) && !isVowel(ch) && ch !== SOFT_SIGN && ch !== "ъ";
}

type Condition = (source: string, start: number, end: number) => boolean;

const CONDITIONS: Readonly<Record<string, Condition>> = {
  default: () => true,
  initial: (_s, i) => i === 0,
  final: (s, _i, j) => j >= s.length,
  after_vowel: (s, i) => i > 0 && isVowel(s[i - 1]!),
  after_consonant: (s, i) => i > 0 && isConsonant(s[i - 1]!),
  after_apostrophe: (s, i) => i > 0 && APOSTROPHES.has(s[i - 1]!),
  after_soft_sign: (s, i) => i > 0 && s[i - 1] === SOFT_SIGN,
  after_l: (s, i) => i > 0 && s[i - 1] === "л",
  before_vowel: (s, _i, j) => j < s.length && isVowel(s[j]!),
  before_soft_vowel: (s, _i, j) => j < s.length && SOFT_VOWELS.has(s[j]!),
  before_consonant: (s, _i, j) => j < s.length && isConsonant(s[j]!),
};

interface CompiledMapping {
  source: string;
  target: string;
  when: readonly string[];
  lossy: boolean;
}

function holds(mapping: CompiledMapping, text: string, start: number, end: number): boolean {
  return mapping.when.some((c) => CONDITIONS[c]!(text, start, end));
}

export class Scheme {
  readonly name: string;
  readonly tests: readonly { input: string; expected: string }[];
  private readonly maxLen: number;
  private readonly bySource: ReadonlyMap<string, readonly CompiledMapping[]>;

  constructor(scheme: TranslitScheme) {
    this.name = scheme.scheme;
    this.tests = scheme.tests;
    const bySource = new Map<string, CompiledMapping[]>();
    let maxLen = 1;
    for (const m of scheme.mappings) {
      const list = bySource.get(m.from) ?? [];
      list.push({ source: m.from, target: m.to, when: m.when.split("|"), lossy: m.lossy });
      bySource.set(m.from, list);
      maxLen = Math.max(maxLen, m.from.length);
    }
    this.bySource = bySource;
    this.maxLen = maxLen;
  }

  /** The longest grapheme at `start` whose condition holds: [output, consumed, lossy]. */
  lookup(text: string, start: number): [string, number, boolean] | null {
    for (let length = Math.min(this.maxLen, text.length - start); length >= 1; length--) {
      const end = start + length;
      const candidates = this.bySource.get(text.slice(start, end));
      if (!candidates) continue;
      for (const mapping of candidates) {
        if (holds(mapping, text, start, end)) return [mapping.target, length, mapping.lossy];
      }
    }
    return null;
  }
}

export interface TransliterationResult {
  text: string;
  unresolved: readonly string[];
}

/** One word, lowercased in, capitalisation re-applied by the caller. */
export function transliterateWord(scheme: Scheme, word: string): TransliterationResult {
  const out: string[] = [];
  const unresolved: string[] = [];
  let i = 0;
  while (i < word.length) {
    const hit = scheme.lookup(word, i);
    if (hit === null) {
      const ch = word[i]!;
      if (!unresolved.includes(ch)) unresolved.push(ch);
      out.push(ch);
      i += 1;
      continue;
    }
    const [target, consumed, lossy] = hit;
    out.push(target);
    if (lossy) {
      const grapheme = word.slice(i, i + consumed);
      if (!unresolved.includes(grapheme)) unresolved.push(grapheme);
    }
    i += consumed;
  }
  return { text: out.join(""), unresolved };
}

export function transliterateToken(scheme: Scheme, word: string): TransliterationResult {
  const result = transliterateWord(scheme, word.toLowerCase());
  return { text: recase(word, result.text), unresolved: result.unresolved };
}
