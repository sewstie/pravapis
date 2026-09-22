// Core value types shared by every layer of the port. Mirrors src/pravapis/types.py.

export type Orthography = "narkamauka" | "taraskievica";

export const OPPOSITE: Record<Orthography, Orthography> = {
  narkamauka: "taraskievica",
  taraskievica: "narkamauka",
};

/** The wire spelling of the *direction*, as opposed to the target orthography. */
export function directionCode(target: Orthography): "n2t" | "t2n" {
  return target === "taraskievica" ? "n2t" : "t2n";
}

export function directionFromCode(code: string): Orthography {
  if (code === "n2t") return "taraskievica";
  if (code === "t2n") return "narkamauka";
  throw new Error(`direction must be 'n2t' or 't2n', got ${JSON.stringify(code)}`);
}

export type Script = "cyrillic" | "lacinka" | "official";

export type Method = "identity" | "lexicon" | "rule" | "model" | "unknown";

export const METHOD_PRIORITY: Record<Method, number> = {
  unknown: 0,
  identity: 1,
  lexicon: 2,
  rule: 3,
  model: 4,
};

export type TokenKind = "word" | "punct" | "space" | "number" | "latin";

export interface Token {
  text: string;
  start: number;
  end: number;
  kind: TokenKind;
}

/** Why a *cross-word* rule fired: what it looked at outside the word itself. Populated
 * only for rules that read a neighbouring word — null positively means the change is
 * reproducible from the word alone. */
export interface ChangeContext {
  trigger: "prev_word_vowel" | "prev_word" | "next_word";
  across?: string;
  rule?: string;
}

export function changeContextToJson(ctx: ChangeContext): Record<string, unknown> {
  const out: Record<string, unknown> = { trigger: ctx.trigger };
  if (ctx.across !== undefined) out.across = ctx.across;
  if (ctx.rule !== undefined) out.rule = ctx.rule;
  return out;
}

export interface Conversion {
  source: string;
  target: string;
  method: Method;
  ruleId: string | null;
  confidence: number;
  /** Code-point offset of `target` in the **output** text; -1 until assigned. */
  start: number;
  end: number;
  citation: string | null;
  context: ChangeContext | null;
}

export function makeConversion(
  source: string,
  target: string,
  method: Method,
  ruleId: string | null = null,
  confidence = 1.0,
  citation: string | null = null
): Conversion {
  return { source, target, method, ruleId, confidence, start: -1, end: -1, citation, context: null };
}

export function changed(conv: Conversion): boolean {
  return conv.source !== conv.target;
}

export function conversionToChange(conv: Conversion): Record<string, unknown> {
  return {
    start: conv.start,
    end: conv.end,
    from: conv.source,
    to: conv.target,
    stage: conv.method,
    rule: conv.ruleId,
    citation: conv.citation,
    context: conv.context === null ? null : changeContextToJson(conv.context),
  };
}

export interface ConversionResult {
  text: string;
  conversions: readonly Conversion[];
  stats: Record<Method, number>;
  direction: Orthography;
  unresolved: readonly string[];
}

export function changesOf(result: ConversionResult): Conversion[] {
  return result.conversions.filter(changed);
}

/** The frozen public wire shape — identical across every implementation of pravapis.
 * See docs/API.md. */
export function conversionResultToDict(
  result: ConversionResult,
  engineVersion: string,
  dataVersion: string
): Record<string, unknown> {
  return {
    text: result.text,
    direction: directionCode(result.direction),
    engine_version: engineVersion,
    data_version: dataVersion,
    changes: changesOf(result).map(conversionToChange),
    unresolved: [...result.unresolved],
  };
}

export interface RuleTrace {
  ruleId: string;
  before: string;
  after: string;
}

export interface TokenExplanation {
  source: string;
  target: string;
  method: Method;
  ruleId: string | null;
  confidence: number;
  traces: readonly RuleTrace[];
}
