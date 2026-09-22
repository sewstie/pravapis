// data/rules/*.yaml -> RuleJson[], mirroring pravapis.rules.engine.load_rules +
// pravapis.dataspec.validate_rules_file. Two things happen here that the Python side
// never needs to: direction aliases are resolved to one of the two canonical long
// forms (so the runtime engine doesn't carry the alias table too), and pattern /
// replacement are translated from the Python `regex` dialect to JS RegExp via
// ./regex-translate.ts. scripts/lint_patterns.py (repo root) is what guarantees every
// pattern *compiles* as JS RegExp; the self-test below additionally checks that the
// translated pattern+replacement *behaves* like the rule's own inline test cases say —
// closing the gap between "compiles" and "does the same thing".

import * as yaml from "js-yaml";
import type { Alternation, Direction, RuleJson, RuleTestCase } from "./types.js";
import { translatePattern, translateReplacement } from "./regex-translate.js";
import { validateAgainstSchema, type Problem } from "./schema.js";

const RESOLVE_DIRECTION: Record<string, Direction> = {
  taraskievica: "narkamauka_to_taraskievica",
  narkamauka: "taraskievica_to_narkamauka",
  narkamauka_to_taraskievica: "narkamauka_to_taraskievica",
  n2t: "narkamauka_to_taraskievica",
  taraskievica_to_narkamauka: "taraskievica_to_narkamauka",
  t2n: "taraskievica_to_narkamauka",
};

function resolveDirection(raw: string): Direction {
  const resolved = RESOLVE_DIRECTION[raw.trim().toLowerCase()];
  if (!resolved) throw new Error(`unknown direction ${JSON.stringify(raw)}`);
  return resolved;
}

const MAX_REPEAT = 8;

interface RawTestCase {
  input: string;
  expected: string;
}
interface RawRule {
  id: string;
  description: string;
  citation: string;
  direction?: string;
  pattern?: string;
  replacement?: string;
  function?: string;
  priority: number;
  repeat?: boolean;
  optional?: boolean;
  requires?: string[];
  exceptions?: string[];
  requires_class?: "loan" | "native";
  alternation?: Alternation;
  tests?: { positive?: RawTestCase[]; negative?: RawTestCase[] };
}
interface RawDoc {
  version?: string;
  group?: string;
  direction?: string;
  rules?: RawRule[];
}

/** Apply one translated rule to `word` exactly as pravapis.rules.engine.Rule.transform
 * does (exceptions short-circuit, `repeat` runs to a fixpoint), so a rule's own inline
 * tests can be checked against the JS-dialect pattern/replacement actually shipped. */
function applyForSelfTest(rule: RuleJson, word: string): string {
  if (rule.exceptions.includes(word)) return word;
  if (!rule.pattern) return word; // function-based: no JS implementation to test here yet
  const re = new RegExp(rule.pattern, "gu");
  if (!rule.repeat) return word.replace(re, rule.replacement ?? "");
  let current = word;
  for (let i = 0; i < MAX_REPEAT; i++) {
    const next = current.replace(re, rule.replacement ?? "");
    if (next === current) break;
    current = next;
  }
  return current;
}

function selfTest(file: string, rule: RuleJson): Problem[] {
  if (rule.requiresClass) return []; // etymology-gated: only the pipeline can supply the stem match
  if (rule.function) return []; // no JS implementation of the named function exists yet to test
  const problems: Problem[] = [];
  for (const t of rule.tests.positive) {
    const got = applyForSelfTest(rule, t.input);
    if (got !== t.expected) {
      problems.push({
        file,
        where: rule.id,
        message: `positive test ${JSON.stringify(t.input)} gave ${JSON.stringify(got)}, expected ${JSON.stringify(t.expected)}`,
      });
    }
  }
  for (const t of rule.tests.negative) {
    const got = applyForSelfTest(rule, t.input);
    if (got !== t.expected) {
      problems.push({
        file,
        where: rule.id,
        message: `negative test ${JSON.stringify(t.input)} was changed to ${JSON.stringify(got)}`,
      });
    }
  }
  return problems;
}

export async function readRulesFile(
  file: string,
  raw: string,
  loadSchema: (name: string) => Promise<Record<string, unknown>>
): Promise<{ rules: RuleJson[]; problems: Problem[] }> {
  const problems: Problem[] = [];
  let doc: unknown;
  try {
    doc = yaml.load(raw);
  } catch (exc) {
    return { rules: [], problems: [{ file, where: "<file>", message: `not valid YAML: ${exc}` }] };
  }

  const schema = await loadSchema("rules");
  problems.push(...validateAgainstSchema(file, schema, doc));
  if (problems.length > 0) return { rules: [], problems }; // a file that fails the schema fails the parser too

  const isFlat = Array.isArray(doc);
  const rawRules: RawRule[] = isFlat ? (doc as RawRule[]) : ((doc as RawDoc).rules ?? []);
  const defaultDirection = isFlat ? undefined : (doc as RawDoc).direction;

  const rules: RuleJson[] = [];
  const seenIds = new Set<string>();
  for (const raw_ of rawRules) {
    const directionRaw = raw_.direction ?? defaultDirection;
    if (!directionRaw) {
      problems.push({ file, where: raw_.id, message: "no direction (file has no default either)" });
      continue;
    }
    const rule: RuleJson = {
      id: raw_.id,
      description: raw_.description,
      citation: raw_.citation,
      direction: resolveDirection(directionRaw),
      priority: raw_.priority,
      repeat: raw_.repeat ?? false,
      optional: raw_.optional ?? false,
      requires: raw_.requires ?? [],
      exceptions: (raw_.exceptions ?? []).map((e) => e.toLowerCase()),
      tests: { positive: raw_.tests?.positive ?? [], negative: raw_.tests?.negative ?? [] },
    };
    if (raw_.requires_class) rule.requiresClass = raw_.requires_class;
    if (raw_.alternation) rule.alternation = raw_.alternation;
    if (raw_.function) {
      rule.function = raw_.function;
    } else if (raw_.pattern) {
      rule.pattern = translatePattern(raw_.pattern);
      rule.replacement = translateReplacement(raw_.replacement ?? "");
      try {
        new RegExp(rule.pattern, "gu");
      } catch (exc) {
        problems.push({
          file,
          where: rule.id,
          message: `translated pattern does not compile as JS RegExp: ${exc}`,
        });
        continue;
      }
    }
    if (seenIds.has(rule.id)) {
      problems.push({ file, where: rule.id, message: "duplicate rule id" });
    }
    seenIds.add(rule.id);
    problems.push(...selfTest(file, rule));
    rules.push(rule);
  }
  return { rules, problems };
}

export type { RuleTestCase };
