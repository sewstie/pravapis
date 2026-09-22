// Lossless tokenizer. `detokenize(tokenize(s)) === s` for every string `s`. Mirrors
// src/pravapis/tokenize.py, reading its word-character tables from generated/chars.json
// instead of a hardcoded copy — see js/src/normalize.ts for the same pattern.
//
// JS Unicode property escapes need `\p{Script=Cyrillic}`, not the bare `\p{Cyrillic}`
// Python's `regex` module accepts; `\p{L}` (General_Category shorthand) is the same in
// both.

import chars from "./generated/chars.json" with { type: "json" };
import type { Token, TokenKind } from "./types.js";

export const APOSTROPHE_CLASS: string = chars.apostrophes.chars.join("");

function escapeForClass(chs: string): string {
  // Only characters that are special inside a [...] class in these strings: - and ^ and ].
  // None of the current apostrophe/letter sets contain them, but a future one might.
  return chs.replace(/[\^\]\\-]/g, "\\$&");
}

const WORD_RE = new RegExp(
  `\\p{Script=Cyrillic}+(?:[${escapeForClass(APOSTROPHE_CLASS)}\\-]\\p{Script=Cyrillic}+)*`,
  "u"
);

const TOKEN_RE = new RegExp(
  `(?<word>\\p{Script=Cyrillic}+(?:[${escapeForClass(APOSTROPHE_CLASS)}\\-]\\p{Script=Cyrillic}+)*)` +
    `|(?<latin>\\p{L}+(?:[${escapeForClass(APOSTROPHE_CLASS)}\\-]\\p{L}+)*)` +
    `|(?<number>\\d+(?:[.,]\\d+)*)` +
    `|(?<space>\\s+)` +
    `|(?<punct>[^\\p{L}\\d\\s]+)` +
    `|(?<other>.)`,
  "gsu"
);

const KIND_BY_GROUP: Record<string, TokenKind> = {
  word: "word",
  latin: "latin",
  number: "number",
  space: "space",
  punct: "punct",
  other: "punct",
};

export function isWordText(text: string): boolean {
  const re = new RegExp(`^${WORD_RE.source}$`, "u");
  return re.test(text);
}

export function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  TOKEN_RE.lastIndex = 0;
  for (const m of text.matchAll(TOKEN_RE)) {
    const groups = m.groups!;
    const kind = (Object.keys(groups).find((k) => groups[k] !== undefined) ??
      "other") as keyof typeof KIND_BY_GROUP;
    const start = m.index!;
    const end = start + m[0].length;
    tokens.push({ text: m[0], start, end, kind: KIND_BY_GROUP[kind]! });
  }
  return tokens;
}

export function detokenize(tokens: readonly Token[]): string {
  return tokens.map((t) => t.text).join("");
}

// Letters of the Belarusian alphabet, both orthographies (ґ is Taraškievica-only).
export const BELARUSIAN_LETTERS: ReadonlySet<string> = new Set(
  chars.alphabet.pairs.map((p) => p.lower)
);
const WORD_CHARS: ReadonlySet<string> = new Set([...BELARUSIAN_LETTERS, ...APOSTROPHE_CLASS, "-"]);
const UPPER_OF: ReadonlyMap<string, string> = new Map(
  chars.alphabet.pairs.map((p) => [p.lower, p.upper])
);
const NOT_BELARUSIAN: ReadonlySet<string> = new Set([
  ...WORD_CHARS,
  ...[...WORD_CHARS].map((c) => UPPER_OF.get(c) ?? c),
]);

/** True when every letter of `token.text` belongs to the Belarusian alphabet.
 * Russian/Ukrainian words (и, щ, ъ, ї …) return false and are passed through
 * untouched rather than half-converted. */
export function isBelarusianWord(token: Token): boolean {
  if (token.kind !== "word") return false;
  return [...token.text].every((ch) => NOT_BELARUSIAN.has(ch));
}

/** The nearest `window` word tokens on each side of `tokens[i]`. */
export function contextOf(tokens: readonly Token[], i: number, window = 2): Token[] {
  const left: Token[] = [];
  for (let j = i - 1; j >= 0 && left.length < window; j--) {
    if (tokens[j]!.kind === "word") left.push(tokens[j]!);
  }
  left.reverse();
  const right: Token[] = [];
  for (let j = i + 1; j < tokens.length && right.length < window; j++) {
    if (tokens[j]!.kind === "word") right.push(tokens[j]!);
  }
  return [...left, ...right];
}

/** The last word token before index `i` with only whitespace in between. */
export function previousWord(tokens: readonly Token[], i: number): Token | null {
  for (let j = i - 1; j >= 0; j--) {
    if (tokens[j]!.kind === "word") return tokens[j]!;
    if (tokens[j]!.kind !== "space") return null;
  }
  return null;
}

//: Збор 2005 §13 Заўвага: a hyphen (злучок) or a quotation mark (двукоссе) between two
//: words is an invisible bridge to the clitic/conjunction/§18 rules.
export const HYPHENS: ReadonlySet<string> = new Set(["-", "‐", "‑", "­"]);
export const QUOTES: ReadonlySet<string> = new Set([
  "«",
  "»",
  "“",
  "”",
  "„",
  "‟",
  "‹",
  "›",
  '"',
]);

/** Is `tokens[i]` transparent to the §13/§18/clitic cross-word rules? True for
 * whitespace and for quotation marks; true for a hyphen only when it is written
 * against a word (a hyphen with space on both sides is a dash, which blocks the
 * rule). */
export function bridgesWords(tokens: readonly Token[], i: number): boolean {
  const token = tokens[i]!;
  if (token.kind === "space") return true;
  if (token.kind !== "punct") return false;
  const text = token.text;
  if ([...text].every((c) => QUOTES.has(c))) return true;
  if (![...text].every((c) => HYPHENS.has(c) || QUOTES.has(c))) return false;
  const touches =
    (i > 0 && tokens[i - 1]!.kind !== "space") || (i + 1 < tokens.length && tokens[i + 1]!.kind !== "space");
  return touches;
}

/** The first word token after index `i`, across whitespace and §13-transparent
 * punctuation. */
export function nextWord(tokens: readonly Token[], i: number): Token | null {
  for (let j = i + 1; j < tokens.length; j++) {
    if (tokens[j]!.kind === "word") return tokens[j]!;
    if (!bridgesWords(tokens, j)) return null;
  }
  return null;
}
