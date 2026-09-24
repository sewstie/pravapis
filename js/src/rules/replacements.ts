/** Apply compiled replacements in order, repeating when softness can propagate
 * leftward. The bound matches the Python rule engine. No tokenization is needed. */
export type Replacement = readonly [RegExp, string];

export function replaceSequentially(
  word: string,
  steps: readonly Replacement[],
  maxPasses = 8
): string {
  for (let pass = 0; pass < maxPasses; pass++) {
    const before = word;
    for (const [pattern, replacement] of steps) {
      word = word.replace(pattern, replacement);
    }
    if (word === before) break;
  }
  return word;
}
