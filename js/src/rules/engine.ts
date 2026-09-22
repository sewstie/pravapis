// Declarative rule engine: applies core.json's `rules` array in priority order for a
// direction, gating etymology-dependent rules on a StemIndex. Mirrors
// src/pravapis/rules/engine.py.

import type { RuleJson } from "../../scripts/lib/types.js";
import type { Orthography } from "../types.js";
import { StemIndex, type StemMatch } from "../lexicon/stem-index.js";
import {
  applyEToEh,
  applyEuPrefix,
  applyFSubstitution,
  applyIToY,
  applyLPalatalization,
  applyStemTarget,
  removeGDistinction,
} from "./loanwords.js";

const MAX_REPEAT = 8;

/** RuleJson.direction ("narkamauka_to_taraskievica" — the orthography a rule
 * *produces*, build-data.ts's already-normalized long form) -> this port's
 * Orthography. */
function ruleTargetOf(direction: RuleJson["direction"]): Orthography {
  return direction === "narkamauka_to_taraskievica" ? "taraskievica" : "narkamauka";
}

export interface RuleTraceEntry {
  ruleId: string;
  before: string;
  after: string;
}

type RuleFunction = (word: string, match: StemMatch | null) => string;

/** 'module:callable' -> the pure function it names. Only the five functions any
 * data/rules/*.yaml rule actually references (see their `function:` fields) —
 * everything else in the rule set is pattern-based and needs no entry here. */
const FUNCTIONS: ReadonlyMap<string, RuleFunction> = new Map<string, RuleFunction>([
  ["pravapis.rules.loanwords:apply_stem_target", (w, m) => applyStemTarget(w, m!)],
  ["pravapis.rules.loanwords:apply_l_palatalization", (w, m) => applyLPalatalization(w, m!)],
  ["pravapis.rules.loanwords:apply_i_to_y", (w, m) => applyIToY(w, m!)],
  ["pravapis.rules.loanwords:apply_e_to_eh", (w, m) => applyEToEh(w, m!)],
  ["pravapis.rules.loanwords:apply_f_substitution", (w) => applyFSubstitution(w)],
  // Not referenced by any current rule (loan.eu / loan.g_remove are pattern-based in
  // the YAML), kept registered so a future data change that switches them to
  // `function:` needs no engine change.
  ["pravapis.rules.loanwords:apply_eu_prefix", (w) => applyEuPrefix(w)],
  ["pravapis.rules.loanwords:remove_g_distinction", (w) => removeGDistinction(w)],
]);

interface CompiledRule extends RuleJson {
  compiled: RegExp | null;
}

export class RuleEngine {
  private readonly rules: readonly CompiledRule[];
  private readonly byDirection: ReadonlyMap<Orthography, readonly CompiledRule[]>;
  private readonly repeatRules: ReadonlyMap<Orthography, readonly CompiledRule[]>;
  private readonly byId: ReadonlyMap<string, CompiledRule>;
  private readonly stems: ReadonlyMap<Orthography, StemIndex>;
  readonly includeOptional: boolean;

  constructor(
    rules: readonly RuleJson[],
    stems: ReadonlyMap<Orthography, StemIndex>,
    includeOptional = false
  ) {
    this.includeOptional = includeOptional;
    this.stems = stems;
    this.rules = rules.map((r) => ({
      ...r,
      compiled: r.pattern !== undefined ? new RegExp(r.pattern, "gu") : null,
    }));
    const byId = new Map<string, CompiledRule>();
    for (const r of this.rules) byId.set(r.id, r);
    this.byId = byId;

    const byDirection = new Map<Orthography, CompiledRule[]>();
    for (const direction of ["narkamauka", "taraskievica"] as const) {
      const forDirection = this.rules
        .filter((r) => ruleTargetOf(r.direction) === direction && (includeOptional || !r.optional))
        .sort((a, b) => (b.priority - a.priority) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
      byDirection.set(direction, forDirection);
    }
    this.byDirection = byDirection;

    const repeatRules = new Map<Orthography, CompiledRule[]>();
    for (const [direction, list] of byDirection) {
      repeatRules.set(direction, list.filter((r) => r.repeat));
    }
    this.repeatRules = repeatRules;
  }

  withOptional(include: boolean): RuleEngine {
    if (include === this.includeOptional) return this;
    return new RuleEngine(this.rules, this.stems, include);
  }

  stemMatch(word: string, direction: Orthography): StemMatch | null {
    return this.stems.get(direction)?.match(word) ?? null;
  }

  get(ruleId: string): RuleJson | undefined {
    return this.byId.get(ruleId);
  }

  citationFor(ruleId: string): string | null {
    return this.byId.get(ruleId)?.citation ?? null;
  }

  private firesOn(rule: CompiledRule, match: StemMatch | null): boolean {
    if (!rule.requiresClass) return true;
    if (match === null || match.cls !== rule.requiresClass) return false;
    return rule.alternation === undefined || match.alternations.includes(rule.alternation);
  }

  private transform(rule: CompiledRule, word: string, match: StemMatch | null): string {
    if (rule.exceptions.includes(word)) return word;
    if (!this.firesOn(rule, match)) return word;
    if (rule.function !== undefined) {
      const fn = FUNCTIONS.get(rule.function);
      if (!fn) throw new Error(`rule ${rule.id}: no JS implementation registered for ${rule.function}`);
      return fn(word, match);
    }
    const re = rule.compiled!;
    if (!rule.repeat) return word.replace(re, rule.replacement ?? "");
    for (let i = 0; i < MAX_REPEAT; i++) {
      const next = word.replace(re, rule.replacement ?? "");
      if (next === word) break;
      word = next;
    }
    return word;
  }

  /** Apply every rule for `direction` and record the ones that changed the word. */
  explain(word: string, direction: Orthography): RuleTraceEntry[] {
    const traces: RuleTraceEntry[] = [];
    const fired = new Set<string>();
    const match = this.stemMatch(word, direction);
    let rules = this.byDirection.get(direction) ?? [];
    for (let pass = 0; pass < MAX_REPEAT; pass++) {
      const before = word;
      for (const rule of rules) {
        if (rule.requires.some((dep) => !fired.has(dep))) continue;
        if (!this.firesOn(rule, match)) continue;
        const next = this.transform(rule, word, match);
        if (next !== word) {
          traces.push({ ruleId: rule.id, before: word, after: next });
          fired.add(rule.id);
          word = next;
        }
      }
      rules = this.repeatRules.get(direction) ?? [];
      if (word === before || rules.length === 0) break;
    }
    return traces;
  }

  apply(word: string, direction: Orthography): [string, string[]] {
    const traces = this.explain(word, direction);
    const ids: string[] = [];
    for (const t of traces) if (!ids.includes(t.ruleId)) ids.push(t.ruleId);
    return [traces.length > 0 ? traces[traces.length - 1]!.after : word, ids];
  }
}
