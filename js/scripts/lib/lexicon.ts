// data/lexicon/loanwords.tsv, exceptions.tsv, proper_nouns.tsv and case/ambiguous.tsv —
// plain TSVs with a `#` comment header and no `#!schema` declaration (dataspec.py does
// not validate these either; see data/MANIFEST and pravapis.dataspec.validate_data).
// Mirrors pravapis.lexicon.builder.read_tsv_pairs: narkamauka<TAB>taraskievica, with an
// optional third column restricting the row to one direction (n2t / t2n), first entry
// for a key wins.

import type { CaseFormsRow, DirectedPairs } from "./types.js";
import type { Problem } from "./schema.js";

type Sanitize = (text: string) => string;

const ONE_WAY = new Set(["n2t", "t2n"]);

function dataLines(raw: string): Array<[number, string]> {
  const out: Array<[number, string]> = [];
  raw.split(/\r?\n/).forEach((line, i) => {
    if (line.trim() && !line.trimStart().startsWith("#")) out.push([i + 1, line]);
  });
  return out;
}

/** narkamauka <-> taraskievica, one map per direction, first entry for a key wins in
 * each — mirrors pravapis.lexicon.builder.build_trie's `table.setdefault`. A row's
 * optional third column restricts it to one direction: `n2t` (or no flag) feeds the
 * forward map keyed by the narkamauka column, `t2n` (or no flag) feeds the reverse map
 * keyed by the taraskievica column. Getting this filter wrong is not cosmetic — 30
 * rows across data/lexicon/*.tsv use it today (e.g. proper_nouns.tsv's `германіі` ->
 * `нямеччыны`/`нямеччыне`, two distinct t2n-only entries that would collide if both
 * directions read every row). */
export function readPairsFile(
  file: string,
  raw: string,
  sanitize: Sanitize
): { pairs: DirectedPairs; problems: Problem[] } {
  const problems: Problem[] = [];
  const n2t: Record<string, string> = {};
  const t2n: Record<string, string> = {};
  for (const [lineNo, line] of dataLines(raw)) {
    const parts = line.split("\t");
    if (parts.length < 2) {
      problems.push({ file, where: `line ${lineNo}`, message: "expected two tab-separated columns" });
      continue;
    }
    const flag = (parts[2] ?? "").trim();
    if (flag && !ONE_WAY.has(flag)) {
      problems.push({
        file,
        where: `line ${lineNo}`,
        message: `third column must be n2t or t2n, got ${JSON.stringify(flag)}`,
      });
      continue;
    }
    const nark = sanitize(parts[0]!.trim());
    const tarask = sanitize(parts[1]!.trim());
    if (flag !== "t2n" && !(nark in n2t)) n2t[nark] = tarask;
    if (flag !== "n2t" && !(tarask in t2n)) t2n[tarask] = nark;
  }
  return { pairs: { n2t, t2n }, problems };
}

/** narkamauka -> {genitive, dativeLocative} (data/lexicon/case/ambiguous.tsv). */
export function readCaseFormsFile(
  file: string,
  raw: string,
  sanitize: Sanitize
): { rows: Record<string, CaseFormsRow>; problems: Problem[] } {
  const problems: Problem[] = [];
  const rows: Record<string, CaseFormsRow> = {};
  for (const [lineNo, line] of dataLines(raw)) {
    const parts = line.split("\t").map((c) => c.trim());
    if (parts.length < 3) {
      problems.push({ file, where: `line ${lineNo}`, message: "expected three tab-separated columns" });
      continue;
    }
    const key = sanitize(parts[0]!);
    if (!(key in rows)) {
      rows[key] = { genitive: sanitize(parts[1]!), dativeLocative: sanitize(parts[2]!) };
    }
  }
  return { rows, problems };
}
