# Versioning the data

The data is versioned **separately from the code**, in [`VERSION`](VERSION), on its own
semver line. `pravapis` the Python package is at one version; the data package it reads
is at another; a future port is at a third. Each implementation declares which *data*
version it implements.

The reason is that the two change for unrelated reasons and at unrelated rates. A stem
added to `stems.tsv` changes what the converter outputs without changing a line of
Python. A profiling pass rewrites the hot loop without changing a single answer. Giving
them one version number forces every such change to be either an overclaim or a silent
one.

## What a bump means

| Bump | Meaning | Examples |
|---|---|---|
| **major** | The *shape* changed. Existing readers break, or silently read the data wrong. | A schema field renamed or removed; a TSV column reordered or its meaning changed; a rule `id` renamed; a condition removed from the transliteration vocabulary; the `$id` of a schema changed. |
| **minor** | Content added, or an optional field added. Existing readers keep working and simply do not exercise the new material. | A stem added to `stems.tsv`; a rule added; a lexicon entry added; a new *optional* schema field; a new alternation code; a new transliteration scheme. |
| **patch** | A correction that adds no new shape and no new entries. | A wrong citation fixed; a typo in a `description`; a stem's `provenance` raised from `derived` to `reviewed`; a test case corrected. |

A stem **added** is a minor. A stem **removed**, or one whose `class` flips from `loan`
to `native`, is also a minor by shape — but it changes existing answers, so it must be
called out in the changelog entry even though the number moves only in the minor place.

A schema field **renamed** is a major. So is a rename that looks cosmetic: a port keys
off those names.

## Who declares what

| Declares | Where | Meaning |
|---|---|---|
| The data | `data/VERSION` | "This is what the data is." |
| Python | `pravapis.dataspec.DATA_VERSION` | "This build implements data version X." |
| A port | its own equivalent constant | the same claim, in its own package |
| The conformance corpus | `conformance/manifest.json` → `data_version` | "These cases were generated from data version X." |

The check runs on load and in CI (`pravapis validate-data`):

* **Major differs** → fatal. The data's shape is not the shape the code reads, and
  converting anyway produces answers that look fine and are not.
* **Data minor is ahead** → a note, not an error. Minor bumps are additive, so older
  code reads newer data correctly; it just does not use all of it.
* **Data minor is behind** → fine, silently. The code knows about material the data
  does not happen to contain.

## Conformance and the data version

`conformance/cases.jsonl` is generated *from* the data, so it is meaningless without
knowing which version produced it. `conformance/manifest.json` records that, plus a
hash of the corpus. A port claims "passes conformance for data 1.2.0", never just
"passes conformance".

Regenerate the corpus on **every** data change — `pravapis export-conformance` — and
commit it in the same change. CI regenerates and diffs; a stale corpus fails the build.
