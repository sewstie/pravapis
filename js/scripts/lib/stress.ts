/** Lossless front coding: each block starts with a full word, followed by
 * shared-prefix-length:suffix records. Blocks bound runtime decoding to 32 words. */
export function encodeStressWords(words: readonly string[]): string[] {
  const sorted = [...new Set(words)].sort();
  const blocks: string[] = [];
  for (let start = 0; start < sorted.length; start += 32) {
    let previous = sorted[start]!;
    const lines = [previous];
    for (const word of sorted.slice(start + 1, start + 32)) {
      let prefix = 0;
      while (prefix < previous.length && previous[prefix] === word[prefix]) prefix++;
      lines.push(`${prefix.toString(36)}:${word.slice(prefix)}`);
      previous = word;
    }
    blocks.push(lines.join("\n"));
  }
  return blocks;
}
