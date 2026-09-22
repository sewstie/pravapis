// The -мент suffix, which Taraškievica writes -мэнт, and which is inherited by
// everything derived from a -мент base noun even after the stress moves. Mirrors
// src/pravapis/morphology.py's MentSuffix, reading its lemma list from
// generated/core.json's `mentLemmas` (decoded at build time from
// morphology/ment_lemmas.marisa — see scripts/lib/marisa-bridge.ts) instead of loading
// the marisa trie directly.

export const MENT_RULE_ID = "loan.ment_suffix";

export class MentSuffix {
  private readonly forms: ReadonlySet<string>;

  constructor(lemmas: readonly string[]) {
    this.forms = new Set(lemmas);
  }

  static empty(): MentSuffix {
    return new MentSuffix([]);
  }

  /** Does this word carry a -мент base, and so inherit its э? Asked of the word as it
   * *arrived*, never of a partly converted one. */
  applies(narkamaukaForm: string): boolean {
    const lw = narkamaukaForm.toLowerCase();
    const mentAt = lw.indexOf("мент");
    if (mentAt === -1) return false;
    const head = lw.slice(0, mentAt + 4);
    for (let i = 0; i <= head.length - 4; i++) {
      if (this.forms.has(head.slice(i))) return true;
    }
    return false;
  }

  static toHard(word: string): string {
    return word.replaceAll("мент", "мэнт").replaceAll("МЕНТ", "МЭНТ").replaceAll("Мент", "Мэнт");
  }

  static toSoft(word: string): string {
    return word.replaceAll("мэнт", "мент").replaceAll("МЭНТ", "МЕНТ").replaceAll("Мэнт", "Мент");
  }
}
