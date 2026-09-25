import assert from "node:assert/strict";
import { test } from "node:test";
import cases from "../../tests/fixtures/orthography_lacinka.json" with { type: "json" };
import { convert } from "../src/index.js";
import { transliterate } from "../src/translit.js";

for (const [nark, tarask, latin] of cases as [string, string, string][]) {
  test(`${nark} → ${tarask} → ${latin} and back`, () => {
    for (const recase of [
      (s: string) => s,
      (s: string) => s[0]!.toUpperCase() + s.slice(1),
      (s: string) => s.toUpperCase(),
    ]) {
      const classical = String(convert(recase(nark), { to: "taraskievica" }).text);
      assert.equal(classical, recase(tarask));
      const encoded = transliterate(classical, "lacinka");
      assert.equal(encoded, recase(latin));
      assert.doesNotMatch(encoded, /[\u0400-\u04ff]/u);
      const decoded = transliterate(encoded, "lacinka", { reverse: true });
      assert.equal(decoded, classical);
      assert.equal(convert(decoded, { to: "narkamauka" }).text, recase(nark));
    }
  });
}
