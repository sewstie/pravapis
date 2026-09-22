// Unicode hygiene applied exactly once at every input boundary. Mirrors
// src/pravapis/normalize.py, reading its tables from generated/chars.json (built from
// data/chars/*.tsv — see scripts/check_charclass_sync.py on the Python side) instead
// of a hardcoded copy.

import chars from "./generated/chars.json" with { type: "json" };

export const CANONICAL_APOSTROPHE: string = chars.apostrophes.canonical;
export const APOSTROPHES: ReadonlySet<string> = new Set(chars.apostrophes.chars);

export const HOMOGLYPH_MAP: ReadonlyMap<string, string> = new Map(
  chars.homoglyphs.pairs.map((p) => [p.latin, p.cyrillic])
);
export const REVERSE_HOMOGLYPH_MAP: ReadonlyMap<string, string> = new Map(
  chars.homoglyphs.pairs.map((p) => [p.cyrillic, p.latin])
);

const ZERO_WIDTH: ReadonlySet<string> = new Set([
  "​", // zero width space
  "‌", // zero width non-joiner
  "‍", // zero width joiner
  "⁠", // word joiner
  "﻿", // byte order mark
  "­", // soft hyphen
]);

const LETTER_RUN = /\p{L}+/gu;
const HAS_CYRILLIC = /\p{Script=Cyrillic}/u;
const HAS_LATIN = /\p{Script=Latin}/u;
const ANY_HOMOGLYPH = new RegExp(`[${[...HOMOGLYPH_MAP.keys()].join("")}]`);
const ANY_REVERSE_HOMOGLYPH = new RegExp(`[${[...REVERSE_HOMOGLYPH_MAP.keys()].join("")}]`);

export function toNfc(text: string): string {
  return text.normalize("NFC");
}

/** Fold look-alike letters towards Cyrillic (or, with `script: "latin"`, the reverse)
 * inside mixed-script letter runs. A run with no letter of the target script is left
 * alone, so a genuine word in the other script survives untouched. */
export function foldHomoglyphs(text: string, script: "cyrillic" | "latin" = "cyrillic"): string {
  if (script === "latin") {
    return text.replace(LETTER_RUN, (run) => {
      if (!ANY_REVERSE_HOMOGLYPH.test(run) || !HAS_LATIN.test(run)) return run;
      return [...run].map((ch) => REVERSE_HOMOGLYPH_MAP.get(ch) ?? ch).join("");
    });
  }
  return text.replace(LETTER_RUN, (run) => {
    if (!ANY_HOMOGLYPH.test(run) || !HAS_CYRILLIC.test(run)) return run;
    return [...run].map((ch) => HOMOGLYPH_MAP.get(ch) ?? ch).join("");
  });
}

export function normalizeApostrophes(text: string, target: string = CANONICAL_APOSTROPHE): string {
  return [...text].map((ch) => (APOSTROPHES.has(ch) ? target : ch)).join("");
}

export function stripZeroWidth(text: string): string {
  return [...text].filter((ch) => !ZERO_WIDTH.has(ch)).join("");
}

/** Compose all four normalisations, in order: NFC, then zero-width stripping (before
 * folding, so an invisible joiner cannot split a letter run in two), then homoglyph
 * folding, then apostrophe normalisation. `script: "latin"` folds the other way, for
 * text arriving in Łacinka on the reverse path. */
export function sanitize(text: string, script: "cyrillic" | "latin" = "cyrillic"): string {
  return normalizeApostrophes(foldHomoglyphs(stripZeroWidth(toNfc(text)), script));
}
