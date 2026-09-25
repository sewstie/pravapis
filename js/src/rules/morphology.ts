// Context-dependent clitics (Збор правілаў 2005, §3 and §29) and the §18/§15 п.4
// Ў <-> У cross-word rule. Mirrors src/pravapis/rules/morphology.py.
//
// GrammarDB first-syllable stress is shared with Python. Unknown forms retain the
// same conservative fallback: monosyllables or a first vowel ё count as stressed.

import { SOFTENERS, SOFT_TRIGGERS, SOFT_VOWELS } from "./palatalization.js";
import type { FunctionWords } from "./function-words.js";
import type { Orthography } from "../types.js";
import type { StressTable } from "../stress.js";

export const VOWELS = new Set(["а", "е", "ё", "і", "о", "у", "ы", "э", "ю", "я"]);

export const CONJ_RULE_ID = "morph.conj_i_j";
export const INITIAL_W_RULE_ID = "morph.initial_u_w";

/** Збор 2005, §13: after a word ending in a vowel, the conjunction і *may* become й.
 * Optional (aggressive mode only) — this port does not implement aggressive mode, so
 * nothing calls this at runtime today; kept for completeness and for a future port of
 * that mode. */
export function conjunctionIToJ(word: string, previousOutput: string): string | null {
  if (word !== "і" && word !== "І") return null;
  if (!previousOutput) return null;
  if (!VOWELS.has(previousOutput[previousOutput.length - 1]!.toLowerCase())) return null;
  return word === "і" ? "й" : "Й";
}

export function syllableCount(word: string): number {
  let n = 0;
  for (const c of word.toLowerCase()) if (VOWELS.has(c)) n++;
  return n;
}

/** Is `word` stressed on its first syllable? Clitics are never stressed. */
export function isFirstSyllableStressed(word: string, words: FunctionWords, stress?: StressTable): boolean {
  if (words.clitics.has(word.toLowerCase())) return false;
  if (stress?.isFirstStressed(word)) return true;
  const lw = word.toLowerCase();
  if (syllableCount(lw) === 1) return true;
  for (const c of lw) {
    if (VOWELS.has(c)) return c === "ё";
  }
  return false;
}

function onePartUToW(word: string, previous: string, words: FunctionWords, stress?: StressTable): string | null {
  if (!word.startsWith("У") || !previous) return null;
  if (!VOWELS.has(previous[previous.length - 1]!.toLowerCase())) return null;
  if (word.length === 1) return null; // "У." — the abbreviated given name
  if (word === word.toUpperCase() && word !== word.toLowerCase()) return null; // an initial abbreviation
  if (words.stressedInitialU.length > 0 && words.hasStressedInitialUPrefix(word.toLowerCase())) {
    return null;
  }
  if (isFirstSyllableStressed(word, words, stress)) return null;
  return "Ў" + word.slice(1);
}

function hyphenatedUToW(word: string, previous: string, words: FunctionWords, stress?: StressTable): string | null {
  const parts = word.split("-");
  const out = [...parts];
  let context = previous;
  let didChange = false;
  for (let i = 0; i < parts.length; i++) {
    const next = onePartUToW(parts[i]!, context, words, stress);
    if (next !== null) {
      out[i] = next;
      didChange = true;
    }
    context = out[i] || context;
  }
  return didChange ? out.join("-") : null;
}

/** Збор 2005, §18: after a vowel, an unstressed initial У becomes Ў. Only capitalised
 * words; three exceptions (stressed у, the abbreviated "У." name, an initial
 * abbreviation); a hyphen is transparent (§18 Заўвага). */
export function initialUToW(word: string, previousOutput: string, words: FunctionWords, stress?: StressTable): string | null {
  if (word.includes("-")) return hyphenatedUToW(word, previousOutput, words, stress);
  return onePartUToW(word, previousOutput, words, stress);
}

/** Правілы 2008, §15 п.4: a proper name never starts with Ў in Narkamaŭka. Categorical
 * — no context needed. Lowercase ў is untouched; an all-caps token is an abbreviation. */
export function initialWToU(word: string): string | null {
  const parts = word.split("-");
  const out = parts.map((part) => {
    const isAllCaps = part === part.toUpperCase() && part !== part.toLowerCase();
    return part.startsWith("Ў") && part.length > 1 && !isAllCaps ? "У" + part.slice(1) : part;
  });
  return out.some((p, i) => p !== parts[i]) ? out.join("-") : null;
}

function softOnset(word: string): boolean {
  if (!word) return false;
  if (SOFT_VOWELS.includes(word[0]!)) return true;
  const head = word.slice(0, 2) === "дз" ? "дз" : word[0]!;
  if (!SOFT_TRIGGERS.has(head)) return false;
  const nextChar = word.slice(head.length, head.length + 1);
  return SOFTENERS.includes(nextChar);
}

/** §29 Заўвага А: an unstressed initial і develops no [й], so з/без/праз stay hard. */
function unstressedInitialI(word: string, words: FunctionWords, stress?: StressTable): boolean {
  return word.slice(0, 1).toLowerCase() === "і" && !isFirstSyllableStressed(word, words, stress);
}

/** Rewrite a clitic given the word that follows it; null when no rule applies. Input
 * is lowercase. Returns the fully converted form (including the soft sign on
 * "бязь"/"зь"). */
export function convertParticle(
  word: string,
  nextWord: string | null,
  direction: Orthography,
  nextTarget: string | null,
  words: FunctionWords,
  stress?: StressTable
): string | null {
  if (direction === "narkamauka") {
    return words.particlesT2n.get(word) ?? null;
  }

  let result: string | null = null;
  if (
    words.particlesN2t.has(word) &&
    nextWord !== null &&
    isFirstSyllableStressed(nextWord, words, stress)
  ) {
    result = words.particlesN2t.get(word)!;
  }
  const base = result ?? word;
  const onsetForm = nextTarget !== null ? nextTarget : nextWord;
  if (
    words.softeningPrepositions.has(base) &&
    nextWord !== null &&
    onsetForm !== null &&
    softOnset(onsetForm.toLowerCase()) &&
    !unstressedInitialI(nextWord, words, stress)
  ) {
    result = base + "ь";
  }
  return result;
}
