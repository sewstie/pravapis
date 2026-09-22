// Decodes a marisa_trie.Trie (a compressed *set* of strings, no values) via a Python
// subprocess, rather than reimplementing marisa's LOUDS binary format in TypeScript.
//
// This is a build-time-only bridge: the shipped package never runs Python, and CI
// already has `uv sync` done in the same job before `npm run build-data` runs (see
// .github/workflows/ci.yml). Used for morphology/ment_lemmas.marisa (116 keys) — small
// enough to embed directly. NOT used for stress/*.marisa (207k + 26k keys): embedding
// that much data would defeat the point of measuring this package's gzipped size, and
// pravapis.rules.morphology.is_first_syllable_stressed already has a documented,
// first-class fallback for "no stress table" (`stress: StressTable | None = None`) —
// this build takes that path deliberately, not as a shortcut. See js/src/rules/
// morphology.ts's module comment for the resulting behavioural gap.

import { execFileSync } from "node:child_process";

export function readMarisaTrieKeys(absPath: string): string[] {
  const script =
    "import marisa_trie, json, sys\n" +
    "t = marisa_trie.Trie()\n" +
    "t.load(sys.argv[1])\n" +
    "print(json.dumps(sorted(t.keys()), ensure_ascii=False))\n";
  const out = execFileSync("uv", ["run", "python", "-c", script, absPath], {
    encoding: "utf-8",
    maxBuffer: 64 * 1024 * 1024,
    env: { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8" },
  });
  return JSON.parse(out) as string[];
}
