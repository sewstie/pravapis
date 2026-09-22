# The pravapis conversion contract

**This document is normative.** Every conversion endpoint, in every implementation,
returns the shape below. A port is not "mostly compatible" — it either returns this or
it is a different API wearing the same name.

The Python side of it is `pravapis.types.ConversionResult.to_dict()` and
`pravapis.api.schemas.ConvertResponse`. Those two and this file are kept in step by
`tests/test_contract.py`; if they ever disagree, this file is right and the code is
wrong.

---

## The response

```json
{
  "text": "Сьнег і плян",
  "direction": "n2t",
  "engine_version": "0.1.0",
  "data_version": "1.3.0",
  "changes": [
    { "start": 0, "end": 5, "from": "Снег", "to": "Сьнег",
      "stage": "rule", "rule": "palat.assim", "citation": "Збор 2005, §29",
      "context": null },
    { "start": 8, "end": 12, "from": "план", "to": "плян",
      "stage": "lexicon", "rule": null, "citation": null,
      "context": null }
  ],
  "unresolved": []
}
```

All six fields are always present. `changes` and `unresolved` may be empty arrays; they
are never `null`, and they are never omitted.

| Field | Type | Meaning |
|---|---|---|
| `text` | string | The converted text. |
| `direction` | `"n2t"` \| `"t2n"` | The direction of travel. |
| `engine_version` | string | The converter that produced this. |
| `data_version` | string | The data package it read. |
| `changes` | array | One entry per word the converter changed, in document order. |
| `unresolved` | array of string | Words the converter declined to decide. Empty unless requested — see "Off by default" below. |

### `direction` names the journey, not the destination

`"n2t"` is Narkamaŭka → Taraškievica; `"t2n"` is the reverse. This is deliberately
*not* the `Orthography` vocabulary (`"narkamauka"` / `"taraskievica"`) that the
**request** uses, because a target orthography alone does not let a reader interpret
`from` and `to`: `"taraskievica"` says where the text arrived and leaves where it
started to inference. Requests name a target; responses name a direction.

### A change

| Field | Type | Meaning |
|---|---|---|
| `start` | integer | Where `to` begins in `text`, in Unicode **code points**. |
| `end` | integer | One past the last code point of `to` in `text`. |
| `from` | string | The word as the input had it. |
| `to` | string | The word as the output has it. |
| `stage` | `identity` \| `lexicon` \| `rule` \| `model` \| `unknown` | Which stage of the cascade resolved it — the *kind* of evidence. |
| `rule` | string \| null | The rule id that fired. `null` for a plain lexicon hit. |
| `citation` | string \| null | Where the evidence comes from: the § of the codification. `null` for a lexicon hit. |
| `context` | object \| null | Set only for cross-word rules. See below. |

`from` is a reserved word in Python and several other languages. It stays `from` on the
wire anyway: the contract is the same in every language, so the language bends.

`rule` and `citation` are both `null` for a plain lexicon hit, and that is not an
omission. A lexicon entry is its own evidence — the answer is that the table says so —
whereas a rule is an argument from a numbered paragraph, and a reader is entitled to
check it. A lexicon hit that *does* carry a rule id (`lex.case_context`) is one where a
rule chose between several entries.

---

## Four decisions, written down

Each of these is a parity bug waiting to happen if it is left implicit. They are the
reason this file exists.

### 1. Offsets are into the output, in Unicode code points

`start` and `end` index **`text`** — the converted string, the one the caller is
holding — not the input. Conversion changes word lengths (`снег` → `сьнег` is four code
points becoming five), so input offsets are not recoverable from the output and would be
useless to anything that wants to highlight what changed.

They count **Unicode code points**, because that is how Python indexes a `str`.
**JavaScript indexes by UTF-16 code unit.** The two are identical for Cyrillic, Latin,
and every character in ordinary Belarusian text, and they part company at the first
character outside the Basic Multilingual Plane:

```
text = "🎉 Сьнег"
       code points:   🎉 = 1   → "Сьнег" starts at 2
       UTF-16 units:  🎉 = 2   → "Сьнег" starts at 3
```

A JS implementation must convert at its own boundary. Slicing the output with a
code-point offset as though it were a UTF-16 index is correct until someone pastes an
emoji, and then silently wrong by one unit per astral character before the change:

```js
// Convert a code-point index (the contract) to a UTF-16 index (what JS strings use).
function cpToUtf16(text, cpIndex) {
  let utf16 = 0;
  for (let cp = 0; cp < cpIndex; cp++) {
    utf16 += String.fromCodePoint(text.codePointAt(utf16)).length; // 1 or 2
  }
  return utf16;
}

function sliceChange(text, change) {
  return text.slice(cpToUtf16(text, change.start), cpToUtf16(text, change.end));
}
```

`Array.from(text)` and `[...text]` iterate by code point and are the other correct
route. `text.length`, `text.slice`, `text.charAt` and `for (i = 0; i < text.length)`
are all UTF-16 and are all wrong without conversion.

**The conformance corpus pins this.** Cases of kind `offsets` carry a `spans` array
alongside `in`/`out`, and several of them contain astral characters. A port that indexes
in UTF-16 produces the right `out` and the wrong `spans`, which every other kind of case
would let through. See `data/eval/offset_cases.tsv`.

### 2. Sanitizer effects are not reported as changes

Input passes through `sanitize()` exactly once at the boundary: NFC composition,
homoglyph folding (Latin `a` typed into a Cyrillic word), apostrophe normalisation to
`’`, and removal of zero-width characters. These edits are real and they do alter
`text`.

They are **not** in `changes`, and no implementation may add them. They are hygiene, not
orthography. A pasted paragraph can easily carry a few dozen curly quotes and stray
Latin letters, and reporting each as a change would bury the handful of actual
conversions the caller asked about. The rule of thumb: `changes` answers "what did the
converter decide?", and the sanitizer decides nothing — it normalises the input so the
converter has one spelling to reason about.

Consequence a port must respect: **`from` is the sanitized form**, not necessarily the
bytes the user typed. A caller that needs to map back to its own original string should
run the same sanitization itself; `sanitize` is idempotent, so doing so is safe.

### 3. `context` is populated for cross-word rules only

Most rules look at one word. Four look at a neighbour, and only those carry a `context`:

| Rule | `trigger` | Reads |
|---|---|---|
| `morph.particle` | `next_word` | не → ня, без → бяз, зь: the following word's stress and soft onset |
| `lex.case_context` | `prev_word` | The preposition before it picks the case (у Нямеччыне vs Нямеччыны) |
| `morph.conj_i_j` | `prev_word_vowel` | §13: і → й after a word ending in a vowel |
| `morph.initial_u_w` | `prev_word_vowel` | §18: У → Ў after a vowel |

```json
{ "trigger": "prev_word_vowel", "rule": "§18" }
{ "trigger": "next_word", "across": "«" }
```

- `trigger` — always present.
- `across` — the non-space characters the rule reached over, or absent when the two
  words were merely adjacent. §18 Заўвага ("Злучок і двукосьсе ня ёсьць знакамі
  прыпынку") makes a hyphen or a quotation mark transparent, so a rule can fire across
  one. That is the part of a firing a reader is least able to reconstruct from the two
  words alone, which is why it is recorded.
- `rule` — the § the *trigger* rests on, when the codification numbers it separately
  from the rule's own `citation`.

**`"context": null` is a positive statement**, not missing data: it says this change is
reproducible from the word alone. A port that omits `context` on a cross-word change is
not merely less informative, it is making a false claim.

Note the asymmetry at `morph.initial_u_w`: forward (`n2t`) it is cross-word, because
§18 only applies after a vowel. Backward (`t2n`) it is not, because Правілы 2008 §15 п.4
is categorical — a proper name never begins with Ў in Narkamaŭka, whatever precedes it.
So the same rule id carries a `context` in one direction and `null` in the other, and
that is correct.

### 4. `engine_version` and `data_version` are independent

They are two version lines and they do not move together.

- **`engine_version`** is the converter — this code. Engine versions move in **lockstep
  across implementations**: a Python `0.4.0` and a JS `0.4.0` implement the same
  contract and the same cascade. That is what makes the number worth reporting.
- **`data_version`** is the data package: rules, lexicon, stems, transliteration tables,
  function words. It has its own semver, documented in `data/VERSIONING.md`, and it
  changes for entirely unrelated reasons. A stem added to `stems.tsv` changes what the
  converter outputs without changing a line of code; a profiling pass rewrites the hot
  loop without changing a single answer.

A bug report needs both. "pravapis says плян" is not reproducible; "engine 0.4.0, data
1.3.0" is. A port declares which **data** version it implements
(`pravapis.dataspec.DATA_VERSION`) and claims conformance against that version, never in
the abstract.

---

## `unresolved`

An array of word forms, in document order, that the converter **saw a decision in and
declined to make**: the word matched an ambiguity trigger (a shape that is sometimes a
loanword and sometimes native — `мяне` looks like the loan `е` class) and no stage of
the cascade resolved it, so it was passed through unchanged.

This is not "every word that did not change". Most Belarusian words are spelled the same
in both orthographies and are correctly left alone; those are silent. `unresolved` is
narrower and more useful: it is the converter declining, on the record.

Silence is the right answer there — a wrong conversion is worse than none — but a silent
silence is indistinguishable from "nothing to do", so it is reported. A UI can grey
these; an evaluation harness can count them.

### Off by default: measured, not guessed

`unresolved` is always present, but **empty unless requested**. Reporting it costs
nothing to compute correctly, but the heuristic behind it (`Converter.is_ambiguous`,
the same regex shape triggers built for the disambiguation classifier's candidate net)
was never validated as something to show a caller directly, so it was measured before
shipping it on:

| Direction | flag precision | flag rate |
|---|---|---|
| N → T | 15.2% | 15.3% |
| T → N | 1.9% | 12.9% |

*Flag precision*: of passthrough words the heuristic flagged, the share that the dev
parallel corpus (`data/corpora/parallel.tsv`, split `dev`) attests really should have
changed — the same in-scope-miss ground truth `pravapis.recall.measure_recall` scores
recall against (`pravapis.recall.measure_unresolved_flag`). *Flag rate*: flagged words
as a share of every dev word token, not just the passthrough ones.

The bar for shipping it unconditionally was **precision ≥ 0.5 and rate ≤ 2%**, in both
directions. It misses both, by a wide margin, in both directions — the trigger shapes
(`[дтнмсзпбвфр]е` matches any consonant followed by е anywhere in a word, not just in a
loanword position) are far too broad for this. So `Converter.convert()` takes
`unresolved: bool = False`: pass `unresolved=True` to compute it anyway. `/v1/convert`
and `/v1/convert/batch` take the same thing as the `?unresolved=true` query parameter
(not a body field — see "Requests" below); without it, `unresolved` is always `[]` on
the wire, same as the library default.

Both figures are ratcheted in `data/eval/baseline.json` alongside recall and precision
(`dev_{n2t,t2n}_unresolved_flag_precision`, `dev_{n2t,t2n}_unresolved_flag_rate`), so a
future heuristic tweak that quietly makes either worse fails `tests/test_ratchet.py`
rather than shipping unnoticed. Revisit shipping it on once the lexicon/stem review
queue (`data/review/stem_candidates.tsv`) has shrunk the false-flag rate — most of the
noise is native vocabulary that happens to contain one of the trigger shapes, exactly
what a bigger stem inventory resolves outright instead of leaving ambiguous.

**The conformance corpus pins this too**, the same way it pins `spans`. Cases of kind
`unresolved` call the reference implementation with `unresolved=true` and record the
list it comes back with alongside `in`/`out`; a port computing a different heuristic —
or none — produces the right `out` and a different `unresolved`, which no other kind of
case would catch. See `data/eval/unresolved_cases.tsv`.

---

## What is *not* in the contract

Two fields exist and are deliberately outside it. A port need not implement either, and
a client must not depend on them.

- **`explanations`** (`/v1/convert` with `"explain": true`) — the per-rule trace: the
  intermediate forms a word passed through. It is a debugging view over the same
  decisions `changes` already reports.
- **`segments`** (`/api/convert` with `"explain": true`) — the whole output as a
  sequence of pieces, including the ones nothing changed. The demo page uses it.

### Transliteration is not conversion

Changing **script** (Cyrillic ↔ Łacinka ↔ the 2007 romanisation) is a different
operation from changing **orthography**, and it has its own response shape
(`TransliterateResponse`: `text`, `script`, `direction`, `unresolved`). The contract on
this page covers orthography conversion only. `/api/convert` will do either depending on
its `script` / `from_script` arguments, and returns the corresponding shape.

---

## Endpoints

| Method | Path | Returns |
|---|---|---|
| `POST` | `/v1/convert` | This contract. |
| `POST` | `/v1/convert/batch` | `{"results": [ <this contract>, … ]}`, up to 100. |
| `POST` | `/api/convert` | This contract (serverless; the same bytes as `/v1/convert`). |
| `POST` | `/v1/transliterate` | `TransliterateResponse` — see above. |
| `GET` | `/v1/lexicon/{word}` | Lookup plus which rules would fire. |
| `GET` | `/v1/stats` | Lexicon size, rule count, model version. |
| `GET` | `/v1/version` | `{engine_version, data_version, data_hash}` — `data_hash` matches the deployed precompiled artifact's filename (`pravapis.artifact`) by construction. |
| `GET` | `/health` | Liveness. |

### Request

```json
{ "text": "Снег і план", "direction": "taraskievica", "explain": false }
```

`direction` on the **request** is the target orthography — `"taraskievica"` or
`"narkamauka"` — not the `n2t`/`t2n` code. The response echoes the journey; the request
names the destination. `text` is capped at 50,000 characters.

`/v1/convert` and `/v1/convert/batch` also take `?unresolved=true` as a query
parameter (not a body field): computes the `unresolved` list this once, at the cost
described in "Off by default" above. Every `/v1/convert` response also carries an
`ETag` header derived from `(text, direction, script, unresolved, data_version)` — an
in-process cache is keyed the same way, so the same five inputs always produce the
same `ETag` and the same body, and a change to any one of them (`?unresolved=true`
included — it changes the response shape) produces a different one.

---

## Privacy

Request text is processed in memory and is not stored or logged. Request logging is
metadata-only — endpoint, direction, character count, duration, engine version, data
version, status — and never the text itself, a hash of it, or a flagged `unresolved`
token, which is still a fragment of user input however short
(`pravapis.api.request_log`; enforced in CI by
`scripts/check_no_request_text_logging.py`).

---

## Changing this contract

Adding a field is a minor engine version. Removing one, renaming one, or changing what
an existing one means is a **major**, and it breaks every port at once — which is the
entire reason the four decisions above are written down rather than left to whoever
reads the Python next.

Anything output-affecting that is not in the data and not in this document is, by
definition, a place where two implementations can disagree. `pravapis conformance
--coverage` audits the first half of that; this file is the second.
