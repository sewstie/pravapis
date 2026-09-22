# Conformance corpus

`cases.jsonl` is the cross-language contract. An implementation of pravapis — this one,
a TypeScript port, anything else — is **correct iff it passes this file**.

Everything here is generated. Do not edit it by hand:

```bash
pravapis export-conformance          # regenerate
pravapis export-conformance --check  # fail if the committed corpus is stale (CI runs this)
```

Regenerate on every data change and commit the result in the same commit. The data
changes what the converter does; a corpus that lags behind it is worse than none,
because it certifies the old behaviour.

## Files

| File | What it is |
|---|---|
| `cases.jsonl` | The contract. Every case here passes in the reference implementation. |
| `known_failures.jsonl` | Same shape. Cases the reference implementation does **not** pass, kept out of the contract and not swept away. |
| `manifest.json` | Which data version produced the corpus, how many cases of each kind, and a sha256 of `cases.jsonl`. |

`known_failures.jsonl` exists because the alternative is to lie in one of two
directions. The gold set measures accuracy, and the converter is at 99.0%, not 100% —
so putting the residue into `cases.jsonl` would mean no implementation could ever pass
it, while silently dropping it would hide known gaps behind a green check. A port is
free to pass cases in `known_failures.jsonl`; that means it is better than the
reference on those, which is worth knowing, and worth moving into the contract.

## Record shape

Described normatively by [`data/schemas/conformance.schema.json`](../data/schemas/conformance.schema.json).

```json
{"id": "rule/palat.assim/pos/0", "kind": "rule", "direction": "narkamauka_to_taraskievica", "script": "cyrillic", "rule": "palat.assim", "in": "снег", "out": "сьнег"}
{"id": "gold/0000", "kind": "gold", "direction": "narkamauka_to_taraskievica", "script": "cyrillic", "in": "…", "out": "…"}
```

JSON Lines: one object per line, UTF-8, LF endings, written byte-identically on every
platform so the `--check` diff means content and not line endings.

## The four kinds, and why the distinction matters

| `kind` | How to run it |
|---|---|
| `rule` | Apply the single rule named in `rule`, **alone**, to `in` — with etymology resolved from the stem inventory if that rule is class-gated. |
| `translit` | Apply the scheme named in `script` directly, with no orthography conversion (the `--no-convert` path). |
| `gold` | Convert the whole string through the public API in `direction`. |
| `heldout` | The same, on genuine Taraškievica nobody derived from a Narkamaŭka source. |

A `rule` case is a **unit** contract and is not the converter's output for that word.
`palat.assim` turns `свіння` into `сьвіння`; the pipeline goes on to write `сьвіньня`.
Running a `rule` case through the full pipeline will fail, for the wrong reason.

## One direction per gold file

`gold` cases are exported N → T only, and `heldout` cases T → N only. This is not an
oversight. `data/eval/gold.tsv` declares `# origin: narkamauka`: its Narkamaŭka side is
the original and its Taraškievica side was written from it by applying the norm. Scoring
the reverse there asks whether the converter can undo a transformation produced by the
same reading of the norm it implements — self-consistency, not accuracy. So the reverse
direction is not exported as a contract from that file, and `gold_t2n.tsv`, which is
genuine Taraškievica, supplies the T → N cases instead.

Round-trip behaviour (N → T → N returning the original) is a property, not a list of
cases, and belongs in a property test on each implementation.

## Claiming conformance

A port claims conformance **for a data version**, never in the abstract:

> passes 885/885 conformance cases for pravapis data 1.0.0

`manifest.json` carries the `data_version` and the sha256 that pin what was actually run.
