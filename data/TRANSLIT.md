# Norm sources for transliteration schemes

Same policy as `data/NORMS.md`: every mapping group traces to a published source, and
`tests/test_norms.py` fails if a scheme in `data/translit/*.yaml` has no entry here or
no `source` field.

**The 2005 codification does not cover the Latin alphabet.** Збор правілаў 2005 has
§1–91 on Cyrillic orthography and nothing else; it only assumes Łacinka exists, noting
in passing the "паралелізм кірылічнага й лацінкавага" spelling, and cites Taraškievič's
1918 grammar in endnote i. So each scheme here needs its own authority, and they are not
of equal strength — the 2007 romanisation is a published state standard, Łacinka is a
tradition with a canonical early witness.

---

## Script is a separate axis from orthography

`Orthography` picks a spelling; `Script` picks a writing system. They compose. But each
Latin scheme shares a **softness convention** with one orthography:

| Scheme | Marks assimilative softness? | Paired with | снег → |
|---|---|---|---|
| Łacinka | yes, as Taraškievica does | Taraškievica | `śnieh` |
| official 2007 | no, as Narkamaŭka does not | Narkamaŭka | `snieh` |

`Converter.render` therefore converts to the paired orthography first, so a Łacinka
reader gets the idiomatic form rather than a merely legible one. `--no-convert`
(`convert=False`) transliterates the input exactly as given.

This pairing is a fact about the schemes, not a convenience: transliterating Narkamaŭka
*снег* into Łacinka gives `snieh`, which is not a spelling any Łacinka text would use.

---

## lacinka — `data/translit/lacinka.yaml`

- direction: Cyrillic → Latin
- source: B. Taraškievič, *Biełaruskaja hramatyka dla škoł* (Vilnia, 1918), łacinka
  edition — the book Збор правілаў 2005 cites in endnote i, and the earliest canonical
  statement of the alphabet used here.
- deviations from modern practice: none recorded so far. Where one is found, log it here
  with both forms rather than silently picking one.

### lat.sibilants
- ж → ž, ч → č, ш → š, дж → dž
- source: Taraškievič 1918, łacinka ed.

### lat.velars
- г → h, ґ → g, х → ch
- source: Taraškievič 1918, łacinka ed. The г/ґ distinction is the same one
  `loan.g_distinction` makes in Cyrillic, and carries its UNVERIFIED status with it —
  but only as an input question: if a text writes ґ, this renders it g.

### lat.softness
- сь → ś, зь → ź, ць → ć, нь → ń, дзь → dź
- source: Taraškievič 1918, łacinka ed.
- note: **softness comes only from ь.** Palatalisation before a soft vowel is carried by
  that vowel's own *i* — сядзіба → siadziba — not by the consonant. Writing *śadziba*
  would be the single most likely error in this table, so it has explicit negative tests.

### lat.iotation
- я ё ю е → ja jo ju je word-initially, after a vowel, after ў, after ь, after an
  apostrophe; → ia io iu ie after a consonant
- source: Taraškievič 1918, łacinka ed.
- the apostrophe is deleted and survives as the *j*: аб’ява → abjava

### lat.l
- л → ł; ль → l; л before a soft vowel → l **and the vowel loses its iotation**:
  лес → les, ляк → lak, лёд → lod, любы → luby
- source: Taraškievič 1918, łacinka ed.
- this is the one place where a consonant absorbs the vowel's *i*, because *l* already
  carries the softness. It is why the scheme needs an `after_l` condition at all.

### lat.soft_sign_bare
- a ь no digraph above consumed → deleted, and reported as **lossy**
- source: none needed — Belarusian has no such sequence (ть, бь, пь are not Belarusian
  words), so this only fires on foreign or malformed input. Marked `lossy: true` so the
  caller is told rather than quietly losing a character.

---

## lacinka_reverse — `data/translit/lacinka_reverse.yaml`

- direction: Latin → Cyrillic
- source: the inverse of the table above, same authority.

### Not an ambiguity: dz
`дз` and `д`+`з` both emit `dz`, and `dz` maps back to the two characters `дз` — which is
byte-identical to what `д`+`з` was. So `дзень` and `адзначыць` both round-trip, and `dź`
has only one source. The apparent ambiguity cancels.

### A real ambiguity: j + vowel
Cyrillic `й` + vowel and the iotated vowel both render as *j* + vowel, so
**найадметнейшых and наядметнейшых are the same Łacinka string** (`najadmietniejšych`)
and the reverse picks the iotated reading. This is not fixable without inventing a
separator the tradition does not use, so it is left as a documented limitation and pinned
by `test_the_j_collision_is_real_and_bounded`. It affects a handful of words: the measured
round trip over the shipped corpus is ≥ 99.9%.

---

## official2007 — `data/translit/official2007.yaml`

- direction: Cyrillic → Latin, **forward only**
- source: Інструкцыя па транслітарацыі геаграфічных назваў Рэспублікі Беларусь літарамі
  лацінскага алфавіта (Дзяржаўны камітэт па зямельных рэсурсах, геадэзіі і картаграфіі,
  2000; as amended 2007), adopted by UNGEGN in 2012 (resolution X/6) as the international
  romanisation system for Belarusian geographical names.
- why no reverse: it does not write assimilative softness, so reading it back into
  Taraškievica would be a guess about softness the source never recorded. Per the
  project's standing policy, pravapis does not guess — `Transliterator.load(reverse=True)`
  raises for this scheme rather than offering a lossy answer.

### Differences from Łacinka worth naming
- л is always `l`, never `ł`
- ль is `ĺ`, never plain `l`, and the vowel after it keeps its iotation

Everything else has the same shape.

---

## Detecting the script

`pravapis.translit.detect_script` returns the script plus **whether the evidence actually
settled it**. Cyrillic is decided by the alphabet. The two Latin schemes share almost
everything — š, č, ž, ŭ, ś, ź, ć, ń and every digraph — and differ in one place that
occurs constantly in running text:

| | hard л | soft ль |
|---|---|---|
| Łacinka | `ł` | `l` |
| official 2007 | `l` | `ĺ` |

So `ł` means Łacinka and `ĺ` means the 2007 scheme. A Latin text with **neither** is
genuinely ambiguous — usually too short to contain an л at all — and detection says so
rather than picking one, because guessing wrong silently corrupts every l in the output.
A text with **both** belongs to no scheme and is refused outright.

## Scheme to scheme

`Converter.transcode` converts between writing systems, detecting the source if not told.
Latin → Latin goes through Cyrillic **and through both orthographies**, because the two
Latin schemes are paired with different ones:

    śnieh  →  сьнег  →  снег  →  snieh
    Łacinka   Taraškievica  Narkamaŭka  official 2007

Skipping the orthography step would hand the official scheme a Taraškievica input and
produce a spelling neither convention uses. Only schemes in `REVERSIBLE` can be read
*from*, so Łacinka → official works and official → Łacinka does not.

## Policy: a scheme is a table, not code

Schemes are YAML with inline tests, read by `pravapis.translit.engine`. Conditions are a
closed vocabulary (`initial`, `after_vowel`, `after_consonant`, `after_apostrophe`,
`after_soft_sign`, `after_l`, `before_soft_vowel`, `before_vowel`, `before_consonant`,
`final`, `default`) rather than regex, so a scheme file can be checked against a published
table by someone who does not read Python. `validate_scheme` asserts every letter of the
Belarusian alphabet is covered, so a blind spot cannot pass characters through unnoticed.
