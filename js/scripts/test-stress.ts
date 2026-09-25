import assert from "node:assert/strict";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import core from "../src/generated/core.json" with { type: "json" };
import type { CoreData } from "./lib/types.js";
import { readMarisaTrieKeys } from "./lib/marisa-bridge.js";
import { encodeStressWords } from "./lib/stress.js";
import { StressTable, hasStressWord } from "../src/stress.js";
import { convert, explain } from "../src/index.js";
import { transliterate } from "../src/translit.js";
import { FunctionWords } from "../src/rules/function-words.js";
import { initialUToW, isFirstSyllableStressed } from "../src/rules/morphology.js";

test("compressed stress lookup preserves every source-table key", () => {
  const data = (core as CoreData).stress!;
  assert.ok(data);
  for (const [key, file] of [
    ["common", "first_stressed.marisa"],
    ["proper", "proper_first_stressed.marisa"],
  ] as const) {
    const words = readMarisaTrieKeys(fileURLToPath(new URL(`../../data/stress/${file}`, import.meta.url)));
    assert.deepEqual(data[key], encodeStressWords(words));
    for (const word of words) assert.ok(hasStressWord(data[key], word), word);
    for (const word of words.filter((_, i) => i % 100 === 0)) {
      assert.equal(hasStressWord(data[key], `${word}#`), false);
    }
  }
});

test("block boundaries, proper-name casing, compounds, and absent words", () => {
  const common = Array.from({ length: 70 }, (_, i) => `слова${String(i).padStart(3, "0")}`);
  const stress = new StressTable({ common: encodeStressWords(common), proper: encodeStressWords(["Іна"]) });
  for (const word of common) assert.ok(stress.isFirstStressed(word));
  assert.ok(stress.isFirstStressed("СЛОВА031"));
  assert.ok(stress.isFirstStressed("Іна"));
  assert.ok(stress.isFirstStressed("Іна-тэст"));
  for (const word of ["", "іна", "ІНА", "слова", "слова070", "-Іна", "тэст-Іна"]) {
    assert.equal(stress.isFirstStressed(word), false, word);
  }
  assert.equal(hasStressWord([], "слова"), false);
});

test("stress lookup respects clitics, fallbacks, and initial У in compounds", () => {
  const words = new FunctionWords((core as CoreData).functionWords);
  const stress = new StressTable({
    common: encodeStressWords(["не"]),
    proper: encodeStressWords(["Утэста"]),
  });
  assert.equal(isFirstSyllableStressed("не", words, stress), false);
  assert.equal(isFirstSyllableStressed("дом", words, stress), true);
  assert.equal(isFirstSyllableStressed("ёлка", words, stress), true);
  assert.equal(isFirstSyllableStressed("квазісінтэтычнае", words, stress), false);
  assert.equal(initialUToW("Утэста-Утэста", "да", words, stress), null);
  assert.equal(initialUToW("Утэста-Утэста", "да", words), "Ўтэста-Ўтэста");
});

for (const [nark, tarask] of [
  ["не ведае", "ня ведае"],
  ["не хоча", "ня хоча"],
  ["не пойдзем", "ня пойдзем"],
  ["не ліпкім", "ня ліпкім"],
  ["не ліпне", "ня ліпне"],
  ["не проста", "ня проста"],
  ["не толькі", "ня толькі"],
  ["без працы", "бяз працы"],
  ["не было", "не было"],
  ["не, ведае", "не, ведае"],
  ["з ідэяй", "з ідэяй"],
  ["з Інаю", "зь Інаю"],
] as const) {
  test(`stress in context: ${nark}`, () => {
    assert.equal(convert(nark, { to: "taraskievica" }).text, tarask);
    assert.equal(explain(nark, { to: "taraskievica" }).map((t) => t.target).join(" "), tarask.replace(",", ""));
    const latin = transliterate(tarask, "lacinka");
    const cyrillic = transliterate(latin, "lacinka", { reverse: true });
    assert.equal(cyrillic, tarask);
    assert.equal(convert(cyrillic, { to: "narkamauka" }).text, nark);
  });
}
