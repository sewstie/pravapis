import assert from "node:assert/strict";
import { test } from "node:test";
import core from "../src/generated/core.json" with { type: "json" };
import type { CoreData } from "./lib/types.js";
import { convert } from "../src/index.js";
import { transliterate } from "../src/translit.js";
import { RuleEngine } from "../src/rules/engine.js";
import {
  markAssimilativeSoftness,
  unmarkAssimilativeSoftness,
} from "../src/rules/palatalization.js";

// Empty stem indexes and no lexicon: these cases must be phonetic rewrites.
const engine = new RuleEngine((core as CoreData).rules, new Map());
const pairs = [
  ["свет", "сьвет"],
  ["снег", "сьнег"],
  ["спеў", "сьпеў"],
  ["звяруга", "зьвяруга"],
  ["сцягам", "сьцягам"],
  ["цвік", "цьвік"],
  ["дзверы", "дзьверы"],
  ["свіння", "сьвіньня"],
  ["рассцілаць", "расьсьцілаць"],
] as const;

for (const [nark, tarask] of pairs) {
  test(`${nark} ↔ ${tarask}: rules, cleanup, and capitalization`, () => {
    assert.equal(markAssimilativeSoftness(nark), tarask);
    assert.equal(markAssimilativeSoftness(tarask), tarask);
    assert.equal(unmarkAssimilativeSoftness(tarask, "’"), nark);
    assert.equal(unmarkAssimilativeSoftness(nark, "’"), nark);
    assert.equal(engine.apply(nark, "taraskievica")[0], tarask);
    assert.equal(engine.apply(tarask, "narkamauka")[0], nark);
    for (const recase of [
      (s: string) => s,
      (s: string) => s[0]!.toUpperCase() + s.slice(1),
      (s: string) => s.toUpperCase(),
    ]) {
      assert.equal(convert(recase(nark), { to: "taraskievica" }).text, recase(tarask));
      assert.equal(convert(recase(tarask), { to: "narkamauka" }).text, recase(nark));
    }
  });
}

test("traditional restrictions and lexical soft signs are preserved", () => {
  for (const word of ["скептык", "склеп", "мацнець", "пэндзлік", "цнянка", "смак", "звон", "спаць", "пісьмо", "касьба", "конь"]) {
    assert.equal(markAssimilativeSoftness(word), word);
    assert.equal(unmarkAssimilativeSoftness(word, "’"), word);
    assert.equal(engine.apply(word, "taraskievica")[0], word);
    assert.equal(engine.apply(word, "narkamauka")[0], word);
  }
  // Whole-word exceptions still take priority over the phonetic pipeline.
  assert.equal(convert("пісьменнік", { to: "taraskievica" }).text, "пісьменьнік");
  assert.equal(convert("пісьменьнік", { to: "narkamauka" }).text, "пісьменнік");
});

test("assimilation precedes script transliteration and round-trips", () => {
  const nark = "Свет, снег!\nСПЕЎ — звяруга.";
  const tarask = "Сьвет, сьнег!\nСЬПЕЎ — зьвяруга.";
  assert.equal(convert(nark, { to: "taraskievica" }).text, tarask);
  const latin = transliterate(String(convert(nark, { to: "taraskievica" }).text), "lacinka");
  assert.equal(latin, "Śviet, śnieh!\nŚPIEŬ — źviaruha.");
  const cyrillic = transliterate(latin, "lacinka", { reverse: true });
  assert.equal(cyrillic, tarask);
  assert.equal(convert(cyrillic, { to: "narkamauka" }).text, nark);
});

test("replacement does not cross word boundaries", () => {
  const text = "с вет; з\nвяруга; ц вік";
  assert.equal(markAssimilativeSoftness(text), text);
});
