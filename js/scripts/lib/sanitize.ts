// Mirrors src/pravapis/normalize.py's sanitize() — only the Cyrillic-target direction,
// which is the only one any data file needs. Data here is curated, not raw user input,
// so homoglyphs are unlikely, but read_stems() and read_tsv_pairs() apply this on the
// Python side and a build that skipped it could silently diverge the moment someone
// pastes a Latin look-alike into a TSV cell.
//
// The homoglyph and apostrophe tables are NOT hardcoded here — they are passed in from
// data/chars/{homoglyphs,apostrophes}.tsv (see ./chars.ts), the same tables
// scripts/check_charclass_sync.py pins src/pravapis/normalize.py's literals against.
// A hardcoded copy here would be exactly the kind of drift risk that check exists to
// catch on the Python side, silently unchecked on this one.

import type { ApostrophesData, HomoglyphsData } from "./types.js";

const ZERO_WIDTH = new Set([
  "​", // zero width space
  "‌", // zero width non-joiner
  "‍", // zero width joiner
  "⁠", // word joiner
  "﻿", // byte order mark
  "­", // soft hyphen
]);

const LETTER_RUN = /\p{L}+/gu;
const HAS_CYRILLIC = /\p{Script=Cyrillic}/u;

function stripZeroWidth(text: string): string {
  return [...text].filter((ch) => !ZERO_WIDTH.has(ch)).join("");
}

/** Builds a `sanitize()` closed over one data build's homoglyph/apostrophe tables,
 * instead of a module-level hardcoded copy of either. */
export function makeSanitizer(
  homoglyphs: HomoglyphsData,
  apostrophes: ApostrophesData
): (text: string) => string {
  const homoglyphMap = new Map(homoglyphs.pairs.map((p) => [p.latin, p.cyrillic]));
  const anyHomoglyph = new RegExp(`[${homoglyphs.pairs.map((p) => p.latin).join("")}]`);
  const apostropheSet = new Set(apostrophes.chars);
  const canonicalApostrophe = apostrophes.canonical;

  function foldHomoglyphs(text: string): string {
    return text.replace(LETTER_RUN, (run) => {
      if (!anyHomoglyph.test(run) || !HAS_CYRILLIC.test(run)) return run;
      return [...run].map((ch) => homoglyphMap.get(ch) ?? ch).join("");
    });
  }

  function normalizeApostrophes(text: string): string {
    return [...text].map((ch) => (apostropheSet.has(ch) ? canonicalApostrophe : ch)).join("");
  }

  return (text: string): string =>
    normalizeApostrophes(foldHomoglyphs(stripZeroWidth(text.normalize("NFC"))));
}
