// Transliteration between Cyrillic and the Latin scripts used for Belarusian. Mirrors
// src/pravapis/translit/__init__.py.

import { sanitize } from "../normalize.js";
import { tokenize } from "../tokenize.js";
import type { Orthography, Script } from "../types.js";
import { Scheme, transliterateToken, type TransliterationResult } from "./engine.js";
import type { TranslitData } from "../../scripts/lib/types.js";

export type { TransliterationResult };
export { Scheme };

/** The orthography each Latin scheme shares a softness convention with. */
export const PAIRED: Readonly<Record<Exclude<Script, "cyrillic">, Orthography>> = {
  lacinka: "taraskievica",
  official: "narkamauka",
};

/** Scripts this port can read back into Cyrillic. The 2007 romanisation is absent on
 * purpose: it does not write assimilative softness, so the reverse cannot be faithful. */
export const REVERSIBLE: ReadonlySet<Script> = new Set(["lacinka"]);

export class Transliterator {
  private readonly scheme: Scheme;

  constructor(scheme: Scheme) {
    this.scheme = scheme;
  }

  static fromData(translit: TranslitData, script: Exclude<Script, "cyrillic">, reverse = false): Transliterator {
    if (reverse && !REVERSIBLE.has(script)) {
      throw new Error(
        `${script} is forward-only: it does not write assimilative softness, so a reverse table could not round-trip`
      );
    }
    const name = reverse ? `${script}_reverse` : script;
    const data = translit.schemes[name];
    if (!data) throw new Error(`no transliteration scheme named ${JSON.stringify(name)}`);
    return new Transliterator(new Scheme(data));
  }

  word(word: string): TransliterationResult {
    return transliterateToken(this.scheme, word);
  }

  /** Only word tokens are transliterated; numbers, punctuation and whitespace are
   * reproduced byte for byte. */
  transliterate(text: string): TransliterationResult {
    const out: string[] = [];
    const unresolved: string[] = [];
    for (const token of tokenize(text)) {
      if (token.kind === "word" || token.kind === "latin") {
        const result = transliterateToken(this.scheme, token.text);
        out.push(result.text);
        for (const ch of result.unresolved) if (!unresolved.includes(ch)) unresolved.push(ch);
      } else {
        out.push(token.text);
      }
    }
    return { text: out.join(""), unresolved };
  }
}

/** Script conversion only — no orthography step. */
export function transliterate(
  translit: TranslitData,
  text: string,
  script: Exclude<Script, "cyrillic">,
  reverse = false
): string {
  const sourceScript: "cyrillic" | "latin" = reverse ? "latin" : "cyrillic";
  return Transliterator.fromData(translit, script, reverse).transliterate(sanitize(text, sourceScript)).text;
}
