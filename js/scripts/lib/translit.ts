// data/translit/*.yaml -> TranslitScheme. No regex dialect to translate here — a
// transliteration scheme is a closed table of (from, to, when) triples matched by
// plain string comparison, not a regex engine, so it is JS-portable as-is; this is
// pure schema validation plus a mechanical rename to camelCase.

import * as yaml from "js-yaml";
import type { TranslitMapping, TranslitScheme } from "./types.js";
import { validateAgainstSchema, type Problem } from "./schema.js";

interface RawMapping {
  from: string;
  to: string;
  when?: string;
  lossy?: boolean;
}
interface RawScheme {
  scheme: string;
  description: string;
  source: string;
  reverse_of?: string;
  mappings: RawMapping[];
  tests: { input: string; expected: string }[];
}

export async function readTranslitFile(
  file: string,
  raw: string,
  loadSchema: (name: string) => Promise<Record<string, unknown>>
): Promise<{ scheme: TranslitScheme | null; problems: Problem[] }> {
  let doc: unknown;
  try {
    doc = yaml.load(raw);
  } catch (exc) {
    return { scheme: null, problems: [{ file, where: "<file>", message: `not valid YAML: ${exc}` }] };
  }

  const schema = await loadSchema("translit");
  const problems = validateAgainstSchema(file, schema, doc);
  if (problems.length > 0) return { scheme: null, problems };

  const rawDoc = doc as RawScheme;
  const mappings: TranslitMapping[] = rawDoc.mappings.map((m) => ({
    from: m.from,
    to: m.to,
    when: m.when ?? "default",
    lossy: m.lossy ?? false,
  }));
  const scheme: TranslitScheme = {
    scheme: rawDoc.scheme,
    description: rawDoc.description,
    source: rawDoc.source,
    mappings,
    tests: rawDoc.tests,
  };
  if (rawDoc.reverse_of) scheme.reverseOf = rawDoc.reverse_of;

  const seen = new Set<string>();
  for (const m of mappings) {
    const key = `${m.from}\t${m.when}`;
    if (seen.has(key)) {
      problems.push({
        file,
        where: m.from,
        message: `a second mapping for ${JSON.stringify(m.from)} under ${m.when} can never be reached`,
      });
    }
    seen.add(key);
  }

  return { scheme, problems };
}
