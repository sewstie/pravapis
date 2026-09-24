import type { StressData } from "../scripts/lib/types.js";

/** Exact lookup without expanding the full GrammarDB word list in memory. */
export function hasStressWord(blocks: readonly string[], word: string): boolean {
  let lo = 0;
  let hi = blocks.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    const block = blocks[mid]!;
    const end = block.indexOf("\n");
    const first = end < 0 ? block : block.slice(0, end);
    if (first <= word) lo = mid + 1;
    else hi = mid;
  }
  if (lo === 0) return false;
  const [first, ...records] = blocks[lo - 1]!.split("\n");
  let current = first!;
  if (current === word) return true;
  for (const record of records) {
    const colon = record.indexOf(":");
    current = current.slice(0, parseInt(record.slice(0, colon), 36)) + record.slice(colon + 1);
    if (current === word) return true;
    if (current > word) return false;
  }
  return false;
}

/** Mirrors Python StressTable, including case-sensitive proper names and compounds.
 * GrammarDB: Aleś Bułojčyk and Uładzimir Koščanka, CC BY-SA 4.0 (see README). */
export class StressTable {
  constructor(private readonly data: StressData) {}

  isFirstStressed(word: string): boolean {
    if (!word) return false;
    if (hasStressWord(this.data.common, word.toLowerCase())) return true;
    const first = word[0]!;
    if (first !== first.toLowerCase() && hasStressWord(this.data.proper, word)) return true;
    const hyphen = word.indexOf("-");
    return hyphen > 0 && this.isFirstStressed(word.slice(0, hyphen));
  }
}
