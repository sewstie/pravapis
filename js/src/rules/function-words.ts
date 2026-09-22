// The function-word inventories: closed lists of particular words that decide what the
// converter outputs. Mirrors src/pravapis/rules/function_words.py, reading from
// generated/core.json's `functionWords` array instead of a TSV file.

import type { FunctionWordRow } from "../../scripts/lib/types.js";

export class FunctionWords {
  readonly particlesN2t: ReadonlyMap<string, string>;
  readonly particlesT2n: ReadonlyMap<string, string>;
  readonly softeningPrepositions: ReadonlySet<string>;
  readonly clitics: ReadonlySet<string>;
  /** Longer stems must not be shadowed by a shorter one that happens to precede it in
   * iteration order, so this is checked with an explicit "does any stem prefix the
   * word" scan, not `Array.prototype.includes`. */
  readonly stressedInitialU: readonly string[];
  readonly dativeLocativePrepositions: ReadonlySet<string>;

  constructor(rows: readonly FunctionWordRow[]) {
    const n2t = new Map<string, string>();
    const t2n = new Map<string, string>();
    const softening = new Set<string>();
    const clitics = new Set<string>();
    const stressed: string[] = [];
    const dative = new Set<string>();
    for (const row of rows) {
      switch (row.role) {
        case "particle_n2t":
          n2t.set(row.form, row.target!);
          break;
        case "particle_t2n":
          t2n.set(row.form, row.target!);
          break;
        case "softening_preposition":
          softening.add(row.form);
          break;
        case "clitic":
          clitics.add(row.form);
          break;
        case "stressed_initial_u":
          stressed.push(row.form);
          break;
        case "dative_locative_preposition":
          dative.add(row.form);
          break;
      }
    }
    this.particlesN2t = n2t;
    this.particlesT2n = t2n;
    this.softeningPrepositions = softening;
    this.clitics = clitics;
    this.stressedInitialU = stressed.slice().sort();
    this.dativeLocativePrepositions = dative;
  }

  static empty(): FunctionWords {
    return new FunctionWords([]);
  }

  hasStressedInitialUPrefix(lowerWord: string): boolean {
    return this.stressedInitialU.some((stem) => lowerWord.startsWith(stem));
  }
}

/** Words whose conversion depends on the next word; never memoised. */
export function contextSensitive(words: FunctionWords): Set<string> {
  return new Set([...words.particlesN2t.keys(), ...words.particlesT2n.keys(), ...words.softeningPrepositions]);
}
