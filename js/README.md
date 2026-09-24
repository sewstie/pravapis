# Pravapis — Belarusian orthography converter

Belarusian orthography conversion between **official orthography (Narkamaŭka)** and
**classical orthography (Taraškievica)**, following the 2005 classical spelling
codification, plus Cyrillic ↔ **Łacinka** transliteration.
For JavaScript and TypeScript, with ESM and CommonJS exports.

[npm](https://www.npmjs.com/package/pravapis) · [Documentation](https://github.com/sewstie/pravapis/blob/main/docs/API.md) · [Па-беларуску](#па-беларуску)

[![npm version](https://img.shields.io/npm/v/pravapis)](https://www.npmjs.com/package/pravapis)
[![CI status](https://github.com/sewstie/pravapis/actions/workflows/ci.yml/badge.svg)](https://github.com/sewstie/pravapis/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/sewstie/pravapis/blob/main/LICENSE)

## Install

```sh
npm install pravapis
```

Requires Node.js 18 or newer. TypeScript declarations are included.

## Convert spelling

```js
import { convert } from "pravapis";

const result = convert("Снег і план сістэмы", { to: "taraskievica" });
console.log(result.text); // "Сьнег і плян сыстэмы"

console.log(convert("сьнег", { to: "narkamauka" }).text); // "снег"
```

For CommonJS, use `const { convert } = require("pravapis");`.

The required `to` option is `"taraskievica"` or `"narkamauka"`. An optional `from`
must name the opposite orthography. The result contains `text`, `direction`
(`"n2t"` or `"t2n"`), `engine_version`, `data_version`, `changes`, and `unresolved`.
Each change includes the source and replacement text and its rule or dictionary
stage. Pass `{ unresolved: true }` as a third argument to collect unresolved words.

Use `explain(text, { to: "taraskievica" })` from `pravapis` for per-word traces.
Import `convert` from `pravapis/names` when you also need the proper-noun dictionary.

## Transliterate

```js
import { transliterate } from "pravapis/translit";

console.log(transliterate("Беларусь", "lacinka")); // "Biełaruś"
console.log(transliterate("Biełaruś", "lacinka", { reverse: true })); // "Беларусь"
```

The script option is `"lacinka"` or `"official"` (the 2007 romanisation scheme).
Transliteration changes the script; use `convert` separately to change orthography.

For traditional Łacinka, convert the orthography first so assimilative soft signs
are present before transliteration. Reverse the steps when returning to Narkamaŭka:

```js
import { convert } from "pravapis";
import { transliterate } from "pravapis/translit";

const classical = convert("Свет, снег, спеў, звяруга", { to: "taraskievica" }).text;
// "Сьвет, сьнег, сьпеў, зьвяруга"
const latin = transliterate(classical, "lacinka");
const cyrillic = transliterate(latin, "lacinka", { reverse: true });
console.log(convert(cyrillic, { to: "narkamauka" }).text);
// "Свет, снег, спеў, звяруга"
```

Assimilation uses sequential regex replacements with no runtime dependencies.
The reverse rules remove assimilative signs while preserving lexical soft signs.

## Па-беларуску

**pravapis** — канвертар беларускага правапісу паміж наркамаўкай (афіцыйным
правапісам) і тарашкевіцай (класічным правапісам), а таксама інструмент
транслітарацыі з кірыліцы ў беларускую лацінку і назад.

Усталюйце пакет камандай `npm install pravapis`. Пакет падтрымлівае JavaScript
і TypeScript, фарматы ESM і CommonJS. Патрабуецца Node.js 18 або навейшы.

```js
import { convert } from "pravapis";

// У класічны правапіс (тарашкевіцу).
console.log(convert("снег", { to: "taraskievica" }).text); // "сьнег"

// У афіцыйны правапіс (наркамаўку).
console.log(convert("сьнег", { to: "narkamauka" }).text); // "снег"
```

Для працы з лацінкай імпартуйце `transliterate` з `pravapis/translit`
(прыклад вышэй). Для пераўтварэння з улікам слоўніка ўласных назваў
імпартуйце `convert` з `pravapis/names`.

Пераўтварэнне заснавана на слоўніках і правілах. Вынік можа патрабаваць
ручной праверкі; гэта не перакладчык з іншых моў на беларускую.

## Accuracy and documentation

Conversion uses dictionaries and spelling rules. Coverage is incomplete, and
output may need review. This package converts Belarusian spelling and script;
it does not translate between languages.

The current source build passes all 1,007 shared conformance cases without waived
failures. It includes the same GrammarDB first-syllable stress data as Python, so
`не ведае → ня ведае` and similar contextual forms no longer rely only on a heuristic.
The tables are stored in compact blocks; lookups decode at most 32 word forms.
No runtime dependencies or network requests are needed, and `pravapis/translit`
remains a separate entry point without the stress data.

Shared Python/JavaScript tests cover `сь/зь/ць/дзь → ś/ź/ć/dź`, `плян → plan`,
`клясыка → klasyka`, `лапа → łapa`, and `сыстэма → systema`, with capitalization and
reverse conversion. Passing this corpus does not imply complete language coverage.

- [Accuracy and known limitations](https://github.com/sewstie/pravapis/blob/main/docs/ACCURACY.md)
- [API reference](https://github.com/sewstie/pravapis/blob/main/docs/API.md)
- [Architecture](https://github.com/sewstie/pravapis/blob/main/docs/ARCHITECTURE.md)
- [Source and Python package](https://github.com/sewstie/pravapis)
- [Report an issue](https://github.com/sewstie/pravapis/issues)

## License

Code: [MIT](https://github.com/sewstie/pravapis/blob/main/LICENSE).
Data licensing varies by source; see
[data/LICENSE](https://github.com/sewstie/pravapis/blob/main/data/LICENSE).

The embedded first-syllable stress tables derive from the
[Belarusian Grammar Database (GrammarDB)](https://github.com/Belarus/GrammarDB)
by Aleś Bułojčyk and Uładzimir Koščanka, under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
Stress marks were reduced to unambiguous first-syllable membership and encoded as
shared-prefix blocks; this derived data retains the same license. Release and
checksum details are recorded in
[data/stress/SOURCE](https://github.com/sewstie/pravapis/blob/main/data/stress/SOURCE).
