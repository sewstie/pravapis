// Thin ajv wrapper over data/schemas/*.schema.json — the NORMATIVE schemas, read
// directly from the repo rather than copied, so there is exactly one place any schema
// is written down. Draft 2020-12, which is what every schema in data/schemas/ declares.

import type { Ajv as AjvInstance, ErrorObject, ValidateFunction } from "ajv";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import path from "node:path";

export interface Problem {
  file: string;
  where: string;
  message: string;
}

// ajv ships as CJS; `ajv/dist/2020`'s type declarations don't resolve cleanly under
// NodeNext's ESM interop, so load it via createRequire.
const require = createRequire(import.meta.url);
const Ajv2020 = require("ajv/dist/2020.js") as new (opts?: Record<string, unknown>) => AjvInstance;

const ajv = new Ajv2020({ allErrors: true, strict: false });

export async function loadSchema(schemaDir: string, name: string): Promise<Record<string, unknown>> {
  const raw = await readFile(path.join(schemaDir, `${name}.schema.json`), "utf-8");
  return JSON.parse(raw) as Record<string, unknown>;
}

function formatError(e: ErrorObject): string {
  return `${e.instancePath || "<document>"} ${e.message ?? "is invalid"}`;
}

/** Validate `instance` (already-parsed YAML/JSON, or a TSV row parsed into an object)
 * against `schema`, returning one Problem per ajv error. `schema`'s own `$id` becomes
 * ajv's cache key, so the same schema object can be validated against repeatedly
 * without recompiling it. */
export function validateAgainstSchema(
  file: string,
  schema: Record<string, unknown>,
  instance: unknown,
  where = "<document>"
): Problem[] {
  const id = schema.$id as string | undefined;
  const validate: ValidateFunction = (id && ajv.getSchema(id)) || ajv.compile(schema);
  if (validate(instance)) return [];
  const errors: ErrorObject[] = validate.errors ?? [];
  return errors.map((e) => ({ file, where, message: formatError(e) }));
}
