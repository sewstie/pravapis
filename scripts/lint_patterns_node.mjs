// Companion to scripts/lint_patterns.py — do not run directly.
//
// The one honest way to know whether a pattern is valid JS RegExp is to ask a JS engine,
// not to guess in Python. Reads a JSON array of pattern strings from stdin, tries
// `new RegExp(pattern, "u")` on each (the "u" flag is what a TS port would compile
// with — it also rejects a few constructs the flagless form silently accepts), and
// writes a JSON array of `{ok, error}` in the same order to stdout.
let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  input += chunk;
});
process.stdin.on("end", () => {
  const patterns = JSON.parse(input);
  const results = patterns.map((pattern) => {
    try {
      new RegExp(pattern, "u");
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : String(e) };
    }
  });
  process.stdout.write(JSON.stringify(results));
});
