// data/lexicon/stems/stems.tsv, mirroring pravapis.lexicon.stems.read_stems +
// pravapis.dataspec.validate_stems_file. The per-row semantic rules (native forbids
// alternations, a cited loan needs a source, an applied loan must be able to fire,
// forward_only is a subset of alternations) live in stems.schema.json's `$defs.row`
// `allOf`, so validating the parsed row against that schema gets them for free instead
// of a second hand-written copy of the same rules.

import type { Alternation, StemRow } from "./types.js";
import { readXTsvSpec, readXTsv } from "./xtsv.js";
import { validateAgainstSchema, type Problem } from "./schema.js";

type Sanitize = (text: string) => string;

const KNOWN_ALTERNATIONS: ReadonlySet<string> = new Set(["l", "i", "e", "g", "eu"]);
const SCHEMA_ID = "tag:pravapis,2026:schema:stems:1";

function parseAlternations(
  file: string,
  lineNo: number,
  raw: string | null
): { alternations: Alternation[]; forwardOnly: Alternation[]; problems: Problem[] } {
  const problems: Problem[] = [];
  if (raw === null) return { alternations: [], forwardOnly: [], problems };
  const codes = new Set<string>();
  const oneWay = new Set<string>();
  for (const token of raw.split(",").map((t) => t.trim())) {
    if (!token) continue;
    const [code, restriction] = token.split(":");
    if (restriction && restriction !== "n2t" && restriction !== "t2n") {
      problems.push({
        file,
        where: `line ${lineNo}`,
        message: `alternation restriction must be n2t or t2n, got ${JSON.stringify(restriction)}`,
      });
      continue;
    }
    codes.add(code!);
    if (restriction === "n2t") oneWay.add(code!);
  }
  for (const code of codes) {
    if (!KNOWN_ALTERNATIONS.has(code)) {
      problems.push({
        file,
        where: `line ${lineNo}`,
        message: `unknown alternation ${JSON.stringify(code)}; known: l, i, e, g, eu`,
      });
    }
  }
  return {
    alternations: [...codes].filter((c) => KNOWN_ALTERNATIONS.has(c)) as Alternation[],
    forwardOnly: [...oneWay] as Alternation[],
    problems,
  };
}

export async function readStemsFile(
  file: string,
  raw: string,
  schemaDir: string,
  loadSchema: (name: string) => Promise<Record<string, unknown>>,
  sanitize: Sanitize
): Promise<{ rows: StemRow[]; problems: Problem[] }> {
  const schema = await loadSchema("stems");
  const spec = readXTsvSpec(schema);
  const { problems, rows: tsvRows } = readXTsv(file, raw, spec, SCHEMA_ID);

  const rowSchema = {
    ...(schema.$defs as Record<string, unknown>).row as Record<string, unknown>,
    $defs: schema.$defs,
  };

  const rows: StemRow[] = [];
  const seen = new Map<string, string>(); // "stem\tanchored" -> class, for the duplicate check
  for (const { lineNo, cells } of tsvRows) {
    const stemRaw = cells.stem ?? "";
    const anchored = !stemRaw.startsWith("-");
    const stem = sanitize(stemRaw.replace(/^-/, "")).toLowerCase();
    const cls = cells.class as "loan" | "native";
    const provenance = cells.provenance as StemRow["provenance"];
    const { alternations, forwardOnly, problems: altProblems } = parseAlternations(
      file,
      lineNo,
      cells.alternations ?? null
    );
    problems.push(...altProblems);

    const row: StemRow = {
      stem,
      anchored,
      class: cls,
      alternations,
      forwardOnly,
      source: cells.source ?? "",
      provenance,
      target: cells.target ?? null,
    };
    problems.push(
      ...validateAgainstSchema(file, rowSchema, {
        stem: row.stem,
        anchored: row.anchored,
        class: row.class,
        alternations: row.alternations,
        forward_only: row.forwardOnly,
        source: row.source,
        provenance: row.provenance,
        target: row.target,
      }, `line ${lineNo}`)
    );

    const key = `${stem}\t${anchored}`;
    const prior = seen.get(key);
    if (prior !== undefined) {
      problems.push({
        file,
        where: `line ${lineNo}`,
        message: `duplicate stem ${JSON.stringify(stem)} (also ${prior})`,
      });
    }
    seen.set(key, cls);
    rows.push(row);
  }
  return { rows, problems };
}
