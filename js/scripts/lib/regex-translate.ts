// Mechanical translation of the two Python regex constructs the JS dialect spells
// differently. Everything else in a pattern (non-capturing groups, lookahead,
// lookbehind, alternation, numbered backreferences *in the pattern itself*, bare
// literals) is already identical in both dialects — that is what scripts/lint_patterns.py
// (the repo root, Python side) exists to guarantee before a pattern ever reaches here:
// it compiles every data/rules/ pattern with both Python's stdlib `re` and Node's
// `new RegExp(p, 'u')` and rejects \w \W \b \B \Z, inline flags, and conditional groups.
// So this module does not re-derive portability; it only rewrites the two spellings
// that differ between the two engines even for a pattern both already accept.

/** `(?P<name>...)` -> `(?<name>...)`. Nothing else in a pattern needs translating. */
export function translatePattern(pySource: string): string {
  return pySource.replace(/\(\?P</g, "(?<");
}

/**
 * Python's `re.sub` replacement dialect (`\1`, `\g<1>`, `\g<name>`) -> JS's
 * (`$1`, `$1`, `$<name>`), walking the string once so an escaped backslash (`\\`) is
 * never mistaken for the start of a backreference, and a literal `$` in the
 * replacement text — none occurs in the shipped data, but a translator that assumes
 * that isn't one — is doubled so JS's `String.prototype.replace` doesn't treat it as
 * its own substitution syntax.
 */
export function translateReplacement(pyReplacement: string): string {
  let out = "";
  let i = 0;
  const n = pyReplacement.length;
  while (i < n) {
    const ch = pyReplacement[i];
    if (ch === "\\" && i + 1 < n) {
      const next = pyReplacement[i + 1];
      if (next === "\\") {
        out += "\\"; // \\  -> literal backslash
        i += 2;
        continue;
      }
      if (next === "g" && pyReplacement[i + 2] === "<") {
        const close = pyReplacement.indexOf(">", i + 3);
        if (close === -1) {
          throw new Error(`unterminated \\g<...> in replacement ${JSON.stringify(pyReplacement)}`);
        }
        const ref = pyReplacement.slice(i + 3, close);
        out += /^\d+$/.test(ref) ? `$${ref}` : `$<${ref}>`;
        i = close + 1;
        continue;
      }
      const digits = /^\d+/.exec(pyReplacement.slice(i + 1));
      if (digits) {
        out += `$${digits[0]}`;
        i += 1 + digits[0].length;
        continue;
      }
      throw new Error(
        `unrecognised escape '\\${next}' in replacement ${JSON.stringify(pyReplacement)}`
      );
    }
    if (ch === "$") {
      out += "$$";
      i += 1;
      continue;
    }
    out += ch;
    i += 1;
  }
  return out;
}
