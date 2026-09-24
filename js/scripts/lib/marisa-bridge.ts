// Decodes a marisa_trie.Trie (a compressed *set* of strings, no values) via a Python
// subprocess, rather than reimplementing marisa's LOUDS binary format in TypeScript.
//
// This is a build-time-only bridge: the shipped package never runs Python, and CI
// already has `uv sync` done in the same job before `npm run build-data` runs (see
// .github/workflows/ci.yml). Used for morphology/ment_lemmas.marisa and the GrammarDB
// stress tables. Stress keys are front-coded before embedding (see stress.ts).

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
