// data/morphology/function_words.tsv — mirrors pravapis.dataspec.validate_function_words_file.
// The per-row shape (particle roles need a target, everything else doesn't) lives in
// function_words.schema.json's `$defs.row`; the cross-row invariants (a softening
// preposition must also be a clitic, a particle_t2n target must be reachable) are not
// expressible in JSON Schema, so they are re-checked here exactly as dataspec.py does.

import type { FunctionWordRow } from "./types.js";
import { readXTsvSpec, readXTsv } from "./xtsv.js";
import { validateAgainstSchema, type Problem } from "./schema.js";

const SCHEMA_ID = "tag:pravapis,2026:schema:function_words:1";

export async function readFunctionWordsFile(
  file: string,
  raw: string,
  loadSchema: (name: string) => Promise<Record<string, unknown>>
): Promise<{ rows: FunctionWordRow[]; problems: Problem[] }> {
  const schema = await loadSchema("function_words");
  const spec = readXTsvSpec(schema);
  const { problems, rows: tsvRows } = readXTsv(file, raw, spec, SCHEMA_ID);

  const rowSchema = {
    ...((schema.$defs as Record<string, unknown>).row as Record<string, unknown>),
    $defs: schema.$defs,
  };

  const rows: FunctionWordRow[] = [];
  const seenFormRole = new Set<string>();
  for (const { lineNo, cells } of tsvRows) {
    const row: FunctionWordRow = {
      form: cells.form ?? "",
      role: cells.role as FunctionWordRow["role"],
      target: cells.target ?? null,
      citation: cells.citation ?? "",
    };
    problems.push(...validateAgainstSchema(file, rowSchema, row, `line ${lineNo}`));
    const key = `${row.form}\t${row.role}`;
    if (seenFormRole.has(key)) {
      problems.push({
        file,
        where: `line ${lineNo}`,
        message: `${JSON.stringify(row.form)} is already listed as ${JSON.stringify(row.role)}`,
      });
    }
    seenFormRole.add(key);
    rows.push(row);
  }

  const clitics = new Set(rows.filter((r) => r.role === "clitic").map((r) => r.form));
  const softeningPrepositions = new Set(
    rows.filter((r) => r.role === "softening_preposition").map((r) => r.form)
  );
  const particlesN2t = new Set(rows.filter((r) => r.role === "particle_n2t").map((r) => r.form));
  const particlesT2n = new Map(
    rows.filter((r) => r.role === "particle_t2n").map((r) => [r.form, r.target] as const)
  );

  for (const preposition of [...softeningPrepositions].sort()) {
    if (!clitics.has(preposition)) {
      problems.push({
        file,
        where: `softening_preposition ${JSON.stringify(preposition)}`,
        message:
          "is not also listed as a clitic, so it would count as a stressed first syllable " +
          "and pull jakanne onto the following word",
      });
    }
  }
  for (const [soft, hard] of [...particlesT2n.entries()].sort(([a], [b]) => (a < b ? -1 : 1))) {
    if (hard !== null && !particlesN2t.has(hard) && !softeningPrepositions.has(hard)) {
      problems.push({
        file,
        where: `particle_t2n ${JSON.stringify(soft)}`,
        message: `reverts to ${JSON.stringify(hard)}, which is neither a particle_n2t nor a softening_preposition — nothing can produce it, so the reverse row is unreachable`,
      });
    }
  }

  return { rows, problems };
}
