import assert from "node:assert/strict";
import { test } from "node:test";
import core from "../src/generated/core.json" with { type: "json" };
import type { CoreData } from "./lib/types.js";
import type { Orthography } from "../src/types.js";
import { convert } from "../src/index.js";
import { StemIndex } from "../src/lexicon/stem-index.js";
import { RuleEngine } from "../src/rules/engine.js";
import { applyIToY, deriveTargetEntries, iToY } from "../src/rules/loanwords.js";

// core.stems is the shared internal whitelist; only loan entries with i license
// this scanner. The reverse spellings are derived from the same entries.
const data = core as CoreData;
const indexes = new Map<Orthography, StemIndex>([
  ["taraskievica", new StemIndex(data.stems)],
  ["narkamauka", new StemIndex(deriveTargetEntries(data.stems))],
]);
const engine = new RuleEngine(data.rules, indexes);

for (const [nark, tarask] of [
  ["сістэма", "сыстэма"],
  ["сістэмамі", "сыстэмамі"],
  ["фізіка", "фізыка"],
  ["фізікай", "фізыкай"],
  ["фізічны", "фізычны"],
  ["апазіцыя", "апазыцыя"],
  ["апазіцыі", "апазыцыі"],
  ["сігналізацыя", "сыгналізацыя"], // suffix -ізацыя is outside the licensed stem
  ["крытыка", "крытыка"],
] as const) {
  test(`${nark} ↔ ${tarask}: whitelisted vowel conversion`, () => {
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

test("native words and stems without an i license bypass the scanner", () => {
  for (const word of ["сіла", "сіні", "сівая", "зіма", "зімовы", "ціха", "цішыня", "сядзіце", "фініш", "лацінскі", "сіці", "пенсія", "марксізм"]) {
    const match = engine.stemMatch(word, "taraskievica");
    if (match !== null) assert.equal(applyIToY(word, match), word);
    assert.ok(!engine.apply(word, "taraskievica")[1].includes("loan.i_to_y"));
  }
});

test("no whitelist means no hardening, even for a known borrowing", () => {
  const empty = new RuleEngine(data.rules, new Map());
  assert.equal(empty.apply("фізіка", "taraskievica")[0], "фізіка");
  assert.equal(empty.apply("фізыка", "narkamauka")[0], "фізыка");
});

test("the primitive scans сі/зі/ці but preserves фі", () => {
  assert.equal(iToY("сізіціфі"), "сызыцыфі");
});
