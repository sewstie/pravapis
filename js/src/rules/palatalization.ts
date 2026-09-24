// Assimilative softness (асіміляцыйная мяккасьць). Mirrors
// src/pravapis/rules/palatalization.py — the reference implementation the YAML rules
// in data/rules/palatalization.yaml must agree with. Used here at runtime only by
// loanwords.ts's deriveTargetEntries (building the reverse etymology index); the
// per-word conversion itself always goes through the (already JS-portable, per
// scripts/lint_patterns.py) YAML rules, never this module directly.

import { replaceSequentially, type Replacement } from "./replacements.js";

export const SOFT_VOWELS = "еёіюя";
export const SOFTENERS = SOFT_VOWELS + "ь";

/** Consonants that soften before a soft vowel and thereby trigger assimilation in the
 * preceding з/с/ц/дз. Velars, hushers, р, д, т never soften. */
export const SOFT_TRIGGERS: ReadonlySet<string> = new Set([
  "в", "м", "п", "б", "л", "н", "с", "з", "ц", "дз",
]);

const TRIGGER_ALT = "(?:дз|[вмпблнсзц])";
const D_PREFIX_LOOKBEHIND = "(?<!^(?:па|за|на|вы|пера|раз|ус|у|з)?(?:а|па|на|пера))";

const APOS_RE = new RegExp(`([зс])[’'ʼ\`‘](?=[${SOFT_VOWELS}])`, "gu");
const GEM_DZ_RE = new RegExp(`${D_PREFIX_LOOKBEHIND}д(?=дз[${SOFTENERS}])`, "gu");
const GEM_RE = new RegExp(`(дз|[нлзсц])(?=\\1[${SOFTENERS}])`, "gu");
const ASSIM_TS_DZ_RE = new RegExp(`(дз|ц)(?=в[${SOFTENERS}])`, "gu");
const ASSIM_RE = new RegExp(`((?<!д)з|с)(?=${TRIGGER_ALT}[${SOFTENERS}])`, "gu");

const UNGEM_DZ_RE = new RegExp(`дзь(?=дз[${SOFTENERS}])`, "gu");
const UNASSIM_RE = new RegExp(`((?<!д)з|с)ь(?=${TRIGGER_ALT}[${SOFTENERS}])`, "gu");
const UNASSIM_TS_DZ_RE = new RegExp(`(дз|ц)ь(?=в[${SOFTENERS}])`, "gu");
const UNGEM_RE = new RegExp(`(дз|[нлзсц])ь(?=\\1[${SOFTENERS}])`, "gu");
const UNAPOS_RE = new RegExp(`([зс])ь(?=[${SOFT_VOWELS}])`, "gu");

const FORWARD_STEPS: readonly Replacement[] = [
  [APOS_RE, "$1ь"],
  [GEM_DZ_RE, "дзь"],
  [GEM_RE, "$1ь"],
  [ASSIM_TS_DZ_RE, "$1ь"],
  [ASSIM_RE, "$1ь"],
];

// Remove assimilation before geminate signs: otherwise the soft trigger to the
// right can disappear before its dependent sign is removed (зьльлю → зллю).
const REVERSE_STEPS: readonly Replacement[] = [
  [UNGEM_DZ_RE, "д"],
  [UNASSIM_RE, "$1"],
  [UNASSIM_TS_DZ_RE, "$1"],
  [UNGEM_RE, "$1"],
];

/** снег → сьнег, свіння → сьвіньня, з'ява → зьява, суддзя → судзьдзя. */
export function markAssimilativeSoftness(word: string): string {
  return replaceSequentially(word, FORWARD_STEPS);
}

/** сьнег → снег, сьвіньня → свіння, зьява → з'ява, судзьдзя → суддзя. */
export function unmarkAssimilativeSoftness(word: string, canonicalApostrophe: string): string {
  word = replaceSequentially(word, REVERSE_STEPS);
  return word.replace(UNAPOS_RE, `$1${canonicalApostrophe}`);
}
