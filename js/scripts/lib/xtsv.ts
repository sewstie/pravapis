// A generic reader for the `x-tsv`-described TSV dialect (data/schemas/stems.schema.json,
// data/schemas/function_words.schema.json): declaration directives, per-column regex
// checks, null tokens. Driven entirely by the schema object rather than hand-coded per
// file, so the schema stays the one place the dialect is written down — mirrors
// pravapis.dataspec's validate_stems_file / read_declaration.

import type { Problem } from "./schema.js";

export interface XTsvColumnSpec {
  name: string;
  index: number;
  required: boolean;
  pattern?: string;
}

export interface XTsvSpec {
  delimiter: string;
  comment: string;
  nullTokens: string[];
  columns: XTsvColumnSpec[];
}

export interface Declaration {
  schemaId: string | null;
  columns: string[];
}

export function readXTsvSpec(schema: Record<string, unknown>): XTsvSpec {
  const spec = schema["x-tsv"] as Record<string, unknown> | undefined;
  if (!spec) throw new Error(`schema ${schema.$id as string} has no x-tsv block`);
  const columns = (spec.columns as XTsvColumnSpec[]).slice().sort((a, b) => a.index - b.index);
  return {
    delimiter: (spec.delimiter as string) ?? "\t",
    comment: (spec.comment as string) ?? "#",
    nullTokens: (spec.nullTokens as string[]) ?? [],
    columns,
  };
}

/** The `#!schema` / `#!columns` directives at the head of the file — comments, so a
 * plain-TSV reader skips them for free, but they are what makes column order a fact
 * about the file rather than a convention a parser has to remember. */
export function parseDeclaration(lines: string[]): Declaration {
  let schemaId: string | null = null;
  let columns: string[] = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    if (!line.startsWith("#")) break; // directives must precede the data
    if (line.startsWith("#!schema")) {
      schemaId = line.slice("#!schema".length).trim() || null;
    } else if (line.startsWith("#!columns")) {
      columns = line
        .slice("#!columns".length)
        .trim()
        .split("\t")
        .map((c) => c.trim())
        .filter((c) => c.length > 0);
    }
  }
  return { schemaId, columns };
}

export interface XTsvRow {
  lineNo: number;
  /** Raw cell text, null-token-normalised to `null`, indexed by column name. */
  cells: Record<string, string | null>;
}

function dataLines(text: string, comment: string): Array<[number, string]> {
  const out: Array<[number, string]> = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;
    if (line.trim() && !line.trimStart().startsWith(comment)) out.push([i + 1, line]);
  }
  return out;
}

/** Declaration problems (schema id / column order), per-cell pattern problems, and the
 * parsed data rows — everything `validateAndReadXTsv`'s caller needs, in one pass. */
export function readXTsv(
  file: string,
  raw: string,
  spec: XTsvSpec,
  expectedSchemaId: string
): { problems: Problem[]; rows: XTsvRow[] } {
  const problems: Problem[] = [];
  const headLines = raw.split(/\r?\n/).slice(0, 20); // directives are always near the top
  const declaration = parseDeclaration(headLines);
  if (declaration.schemaId === null) {
    problems.push({
      file,
      where: "<declaration>",
      message: `no '#!schema' directive; expected ${expectedSchemaId}`,
    });
  } else if (declaration.schemaId !== expectedSchemaId) {
    problems.push({
      file,
      where: "<declaration>",
      message: `declares schema ${declaration.schemaId}, but this build implements ${expectedSchemaId}`,
    });
  }
  const declaredOrder = spec.columns.map((c) => c.name);
  if (declaration.columns.length === 0) {
    problems.push({ file, where: "<declaration>", message: "no '#!columns' directive" });
  } else if (
    JSON.stringify(declaration.columns) !==
    JSON.stringify(declaredOrder.slice(0, declaration.columns.length))
  ) {
    problems.push({
      file,
      where: "<declaration>",
      message: `declares columns ${JSON.stringify(declaration.columns)}, but the schema orders them ${JSON.stringify(declaredOrder)}`,
    });
  }

  const required = spec.columns.filter((c) => c.required).length;
  const patterns = spec.columns.map((c) => (c.pattern ? new RegExp(c.pattern) : null));
  const rows: XTsvRow[] = [];
  for (const [lineNo, line] of dataLines(raw, spec.comment)) {
    const rawCells = line.split(spec.delimiter).map((c) => c.trim());
    if (rawCells.length < required) {
      problems.push({
        file,
        where: `line ${lineNo}`,
        message: `${rawCells.length} columns, needs at least ${required}`,
      });
      continue;
    }
    if (rawCells.length > spec.columns.length) {
      problems.push({
        file,
        where: `line ${lineNo}`,
        message: `${rawCells.length} columns, schema declares ${spec.columns.length}`,
      });
      continue;
    }
    const cells: Record<string, string | null> = {};
    rawCells.forEach((cell, idx) => {
      const col = spec.columns[idx];
      if (!col) return;
      if (patterns[idx] && !patterns[idx]!.test(cell)) {
        problems.push({
          file,
          where: `line ${lineNo}`,
          message: `column ${col.name}: ${JSON.stringify(cell)} does not match ${col.pattern}`,
        });
      }
      cells[col.name] = spec.nullTokens.includes(cell) ? null : cell;
    });
    rows.push({ lineNo, cells });
  }
  return { problems, rows };
}
