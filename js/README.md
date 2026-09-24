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

- [Accuracy and known limitations](https://github.com/sewstie/pravapis/blob/main/docs/ACCURACY.md)
- [API reference](https://github.com/sewstie/pravapis/blob/main/docs/API.md)
- [Architecture](https://github.com/sewstie/pravapis/blob/main/docs/ARCHITECTURE.md)
- [Source and Python package](https://github.com/sewstie/pravapis)
- [Report an issue](https://github.com/sewstie/pravapis/issues)

## License

Code: [MIT](https://github.com/sewstie/pravapis/blob/main/LICENSE).
Data licensing varies by source; see
[data/LICENSE](https://github.com/sewstie/pravapis/blob/main/data/LICENSE).
