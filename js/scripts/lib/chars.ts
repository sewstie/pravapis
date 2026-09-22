// data/chars/{alphabet,apostrophes,homoglyphs}.tsv — the shared primitives every
// implementation's tokenizer and sanitizer needs: the word-character class, the
// case-fold table (deliberately NOT `str.casefold()` / `String.toLowerCase()`, which
// are not guaranteed to agree across language runtimes on every Unicode range), and
// the homoglyph-fold table. See the schemas for the normative shape of each file.

import type { AlphabetData, ApostrophesData, HomoglyphsData } from "./types.js";
import { readXTsvSpec, readXTsv } from "./xtsv.js";
import { validateAgainstSchema, type Problem } from "./schema.js";

export async function readAlphabetFile(
  file: string,
  raw: string,
  loadSchema: (name: string) => Promise<Record<string, unknown>>
): Promise<{ data: AlphabetData | null; problems: Problem[] }> {
  const schema = await loadSchema("alphabet");
  const spec = readXTsvSpec(schema);
  const { problems, rows } = readXTsv(file, raw, spec, "tag:pravapis,2026:schema:alphabet:1");

  const pairs = rows.map((r) => ({ lower: r.cells.lower ?? "", upper: r.cells.upper ?? "" }));
  problems.push(...validateAgainstSchema(file, schema, pairs));

  const seenLower = new Set<string>();
  const seenUpper = new Set<string>();
  for (const { lineNo, cells } of rows) {
    const lower = cells.lower ?? "";
    const upper = cells.upper ?? "";
    if (seenLower.has(lower)) {
      problems.push({ file, where: `line ${lineNo}`, message: `${JSON.stringify(lower)} already listed` });
    }
    seenLower.add(lower);
    if (seenUpper.has(upper)) {
      problems.push({ file, where: `line ${lineNo}`, message: `${JSON.stringify(upper)} already listed` });
    }
    seenUpper.add(upper);
  }

  return { data: { pairs }, problems };
}

export async function readApostrophesFile(
  file: string,
  raw: string,
  loadSchema: (name: string) => Promise<Record<string, unknown>>
): Promise<{ data: ApostrophesData | null; problems: Problem[] }> {
  const schema = await loadSchema("apostrophes");
  const spec = readXTsvSpec(schema);
  const { problems, rows } = readXTsv(file, raw, spec, "tag:pravapis,2026:schema:apostrophes:1");

  const pairs = rows.map((r) => ({ char: r.cells.char ?? "", canonical: r.cells.canonical ?? "" }));
  problems.push(...validateAgainstSchema(file, schema, pairs));

  const canonicals = new Set(pairs.map((p) => p.canonical));
  if (canonicals.size !== 1) {
    problems.push({ file, where: "<file>", message: `more than one canonical value: ${[...canonicals].join(", ")}` });
    return { data: null, problems };
  }
  const [canonical] = [...canonicals];
  const chars = pairs.map((p) => p.char);
  if (!chars.includes(canonical!)) {
    problems.push({ file, where: "<file>", message: "the canonical value is not itself a listed char" });
  }

  return { data: { canonical: canonical!, chars }, problems };
}

export async function readHomoglyphsFile(
  file: string,
  raw: string,
  loadSchema: (name: string) => Promise<Record<string, unknown>>
): Promise<{ data: HomoglyphsData | null; problems: Problem[] }> {
  const schema = await loadSchema("homoglyphs");
  const spec = readXTsvSpec(schema);
  const { problems, rows } = readXTsv(file, raw, spec, "tag:pravapis,2026:schema:homoglyphs:1");

  const pairs = rows.map((r) => ({ latin: r.cells.latin ?? "", cyrillic: r.cells.cyrillic ?? "" }));
  problems.push(...validateAgainstSchema(file, schema, pairs));

  return { data: { pairs }, problems };
}
