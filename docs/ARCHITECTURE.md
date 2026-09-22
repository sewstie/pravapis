# Architecture

pravapis is a rule-transducer + compressed-lexicon cascade whose distinguishing choices
are: etymology lives in data, not in code, so a loanword rule and the native word that
would otherwise collide with it are both one-line data edits; every rule and every
transliteration mapping carries a citation, so a change the converter makes can be
checked against the codification it claims to implement rather than trusted on faith;
and the data format is specified independently of any one implementation (JSON Schemas
in `data/schemas/`, a generated cross-language conformance corpus), so a Python
library, a CLI, an HTTP API and an npm package can all read the same rules and agree
byte-for-byte on the answer.

## How it works

Each word goes through a cascade. The first stage that resolves it wins:

| # | Stage | Method | Example |
|---|---|---|---|
| 1 | Never-changes set | `identity` | `і`, `у` |
| 2 | Lexicon (marisa-trie, case-folded, case re-applied) | `lexicon` | `сімвал → сымбаль` |
| 3 | YAML rule engine (regex, priority-ordered, fixpoint for chained softness) | `rule` | `свіння → сьвіньня` |
| 4 | Passthrough | `unknown` | most words are spelled the same in both |

The loanword rules at stage 3 are **gated on etymology**, which is a data file rather
than a pattern: `data/lexicon/stems/stems.tsv` says whether a stem is a borrowing, and
soft л / і → ы / е → э fire only inside a stem classed `loan`. Longest match wins, so a
false friend is a native stem one character longer than the loan stem it must beat
(`класц` over `клас`), and no rule carries a lookahead. See
[Etymology is data](../data/NORMS.md).

The lexicon comes before the rules because loanwords are exactly what the rules get wrong.
Words that neither stage resolves are left unchanged: leaving a word alone is better than
getting it wrong.

An experimental classifier exists in `src/pravapis/disambiguate/` but is **off by default** and
not part of the architecture above; see [Why the classifier was removed](ACCURACY.md#why-the-classifier-was-removed).

Rules live in `data/rules/*.yaml` and include inline positive/negative test cases. The test
suite runs those cases and checks that the YAML agrees with the pure-Python reference
implementations in `src/pravapis/rules/`.

## Transliteration

Script is a second axis, orthogonal to orthography. `Orthography` picks a spelling,
`Script` picks a writing system, and they compose.

```
$ pravapis translit "снег і свет" --to lacinka
śnieh i śviet
$ pravapis translit "снег" --to official
snieh
$ pravapis translit "śnieh i śviet" --from lacinka
сьнег і сьвет
$ pravapis translit "śnieh i śviet" --from auto --to official
snieh i sviet
```

They are not independent in practice, and that is the design's one real decision.
**Łacinka marks assimilative softness exactly as Taraškievica does** (сьнег → śnieh);
**the 2007 national romanisation marks only the ь that is written, as Narkamaŭka does**
(снег → snieh). Each Latin scheme therefore shares a softness convention with one
orthography, and `render` converts to the paired orthography first so the output is
idiomatic rather than merely legible. `--no-convert` transliterates the input as given.

| Scheme | Direction | Source |
|---|---|---|
| `lacinka` | both ways | Taraškievič, *Biełaruskaja hramatyka dla škoł* (1918), łacinka ed. |
| `official` | forward only | Інструкцыя па транслітарацыі… (2000, amended 2007); UNGEGN 2012 |

`--from auto` detects the script. Cyrillic is decided by the alphabet; the two Latin
schemes are told apart by the one letter that distinguishes them — Łacinka writes hard л
as `ł`, the 2007 scheme writes soft ль as `ĺ`. Text with neither is genuinely ambiguous
and detection says so instead of guessing; text with both is refused. Scheme-to-scheme
(`--from lacinka --to official`) routes through Cyrillic *and* both orthographies, since
each Latin scheme is paired with a different one.

`official` is forward-only on purpose: it does not write assimilative softness, so
reading it back would be a guess about something the source never recorded, and this
project does not guess — `Transliterator.load(reverse=True)` raises for it.

Schemes are YAML tables with inline tests (`data/translit/*.yaml`), read by a
longest-match single-pass transducer. Conditions are a closed vocabulary
(`after_vowel`, `after_consonant`, `after_l`, …) rather than regex, so a scheme can be
checked against a published table by someone who does not read Python. Every letter of
the alphabet must be covered, or the tests fail. Sources and the two known limitations
are in [`data/TRANSLIT.md`](../data/TRANSLIT.md).

Measured: Łacinka round-trips **≥ 99.9%** of the Taraškievica words the project ships
(lexicon targets, gold set and mining corpus). The residue is one genuine collision —
Cyrillic `й` + vowel and the iotated vowel are the same Łacinka string, so
`найадметнейшых` and `наядметнейшых` both give `najadmietniejšych` — plus a bare `ь`
after a consonant with no soft Latin counterpart, which is reported as `unresolved`
rather than silently dropped.

### Finding false friends before they fire

Longest-match means a loan stem silently claims every word starting with it.
`scripts/check_stem_collisions.py` asks GrammarDB's 224,669 lemmas which words each loan
stem would also match, and reports the ones no native guard covers:

```bash
python scripts/check_stem_collisions.py RELEASE-202601.zip
```

It found false positives the gold set never reached — `клуб` also claims the native root
`клубень` ("tuber"), and `салон` claims `салонец`, a soil type — both now guarded with
stems short enough to spare `клубе` and `клубам`. Most of what it reports is *not* a
collision (`рэклама` and `дакументаабарот` are the same lexeme and should convert), so the
output is a review queue rather than a patch.

This replaced the runtime lemma-confirmation layer originally planned here. Measured
first: of 51 native guards, only **3** changed any answer, so a per-lookup confirmation
table would have added a data file and a deployment payload to solve a problem worth three
rows. `data/NORMS.md` records the measurement.

## Performance

`pravapis bench --size 10mb` reports **1.2 MB/s, ~93k words/s**, single process. On real
corpus text (`roundtrip_corpus.txt`) it is 0.84 MB/s, up from 0.54 before this pass — a
**55% gain**, from profiling rather than guessing.

The roadmap had a C++ lexicon lookup here. **The profile says don't write it**: lexicon
lookup does not appear in the top sixteen entries at all. The cost was somewhere else
entirely, and all of it was work being thrown away:

| Fix | Why it was wasted |
|---|---|
| Skip `context_of` with no classifier | The neighbouring-word context exists only to featurise a word for the classifier, which is off by default. It was built for every token and discarded. |
| Look up neighbours only for clitics | `next_word`/`previous_word` ran for every token, but only не/без/з and the case-dependent lexicon read them. |
| Bail out of homoglyph folding early | Ordinary Belarusian text contains no Latin look-alikes, so every letter run was rebuilt character by character to produce itself. |
| One regex instead of a per-character genexpr | `is_belarusian_word` allocated a generator per token. |
| Tighten the `tokenize` loop | It is the one loop that runs over the entire input. |

marisa-trie is already C; the Python around it was the cost. A pybind11 extension would
have optimised the one part that was never slow.

## The data is a specification

Every data file is described by a JSON Schema in [`data/schemas/`](../data/schemas/), and
those schemas are **normative**. An implementation in another language reads them; it
does not read `src/pravapis/rules/engine.py` and infer the format from whatever the
parser happens to tolerate.

| Schema | Describes |
|---|---|
| `rules.schema.json` | `data/rules/*.yaml` — both accepted layouts, the pattern/function alternative, the etymology gate |
| `stems.schema.json` | `data/lexicon/stems/*.tsv` — the file dialect in `x-tsv`, the parsed row in `$defs/row` |
| `translit.schema.json` | `data/translit/*.yaml` — the closed condition vocabulary, coverage |
| `conformance.schema.json` | one line of `conformance/cases.jsonl` |
| `alphabet.schema.json`, `apostrophes.schema.json`, `homoglyphs.schema.json` | `data/chars/*.tsv` — the shared word-character, case-fold and homoglyph tables every implementation's tokenizer/sanitizer reads |

`stems.tsv` is TSV, so it **declares its own header** — the schema it is written against
and the order of its columns — in `#!schema` / `#!columns` directives. They are comments,
so every existing reader skips them for free, and column order becomes a fact about the
file rather than a fact about whichever parser reads it.

Every rule carries a required `citation`: a § of Збор правілаў 2005, or
`derived:<rule-id>` for an inverse, or `convention:<reason>`. A rule that cannot say why
it fires does not belong in the inventory — and the citation is surfaced on every change
the converter reports.

```bash
pravapis validate-data     # schemas + the semantics JSON Schema cannot state
```

That last part matters: cycle detection in rule dependencies, stem duplicates, alphabet
coverage for a scheme and the inline rule tests all run in the same command, because a
file can satisfy the schema and still be wrong, and a contributor should not have to know
which gate catches what. CI runs it before the test suite.

## Versioning: the data moves separately from the code

[`data/VERSION`](../data/VERSION) carries its own semver, and
[`data/VERSIONING.md`](../data/VERSIONING.md) says what a bump means — a stem added is a
**minor**, a schema field renamed is a **major**. Each implementation declares the data
version it implements (`pravapis.DATA_VERSION`); a major mismatch is fatal rather than
silently wrong.

They change for unrelated reasons at unrelated rates. A stem added to `stems.tsv`
changes what the converter outputs without touching a line of Python; a profiling pass
rewrites the hot loop without changing a single answer. One version number for both
forces every such change to be either an overclaim or a silent one.

## Conformance: the cross-language contract

```bash
pravapis export-conformance          # regenerate
pravapis export-conformance --check  # CI: fail if the committed corpus is stale
```

[`conformance/cases.jsonl`](../conformance/) flattens every inline rule test, every inline
transliteration test, the trusted gold subset and the independent held-out sentences into
one file of self-contained cases. **A port is correct iff it passes it.** `manifest.json`
records the data version and a sha256, because a port claims conformance *for a data
version*, never in the abstract. The npm package's `npm test` replays the same file
against the JS engine (`js/scripts/test-conformance.ts`).

Each case says at which level it applies — `rule` cases exercise one rule in isolation,
`gold` and `heldout` cases go through the public API, `offsets` and `unresolved` cases
additionally pin the code-point spans and the ambiguity-flag list — since running a unit
case through the whole pipeline would fail for the wrong reason (`palat.assim` turns
`свіння` into `сьвіння`; the pipeline goes on to write `сьвіньня`).

Two decisions worth stating:

- **Only one direction is exported per gold file.** `gold.tsv` declares
  `# origin: narkamauka`, so contracting T → N from it would freeze a self-consistency
  figure as though it were accuracy. The T → N cases come from the genuine Taraškievica
  set instead.
- **Cases the reference implementation does not pass go to
  `known_failures.jsonl`**, not into the contract. Putting them in `cases.jsonl` would
  make it unpassable; dropping them would hide known gaps behind a green check. The npm
  package documents its own, narrower set of known gaps (no GrammarDB stress table) in
  `js/scripts/known-gaps.json`.

## Serverless deployment (Vercel)

This repository deploys as its own Vercel project: a demo page at `/` and a Python
function at `/api/convert`. No FastAPI, no build step.

| File | Role |
|---|---|
| `api/convert.py` | Vercel Python function; thin `BaseHTTPRequestHandler` over `pravapis.webapi` |
| `src/pravapis/webapi.py` | validation, CORS, JSON shapes (stdlib + the converter only) |
| `data/pravapis-<hash>.bin` | the precompiled artifact `api/convert.py` loads at import — see below |
| `requirements.txt` | runtime deps for the function: regex, marisa-trie, PyYAML, pydantic |
| `vercel.json` | static output from `public/`; tests, benchmarks, scripts, `data/eval` excluded from the function bundle |
| `public/index.html` | the page at `/`: a plain form, single file, no framework |

`POST /api/convert` takes `{"text", "direction", "explain"}` — plus `"script"`
(`lacinka` / `official`), `"from_script"` and `"convert"` for transliteration — and
returns `{"result", "direction", "script", "stats"}`, plus `segments` (every word with its method, rule id and rule trace)
when `explain` is true. The page itself sends only `text` and `direction`. Cross-origin calls are allowed from `https://paznaj.by`,
`https://www.paznaj.by` and `http://localhost` / `http://127.0.0.1` on any port; `OPTIONS`
preflight is answered with 204.

### Precompiled artifact

`api/convert.py` no longer builds a `Converter` from YAML and TSV sources at cold
start. It loads `data/pravapis-<data-hash>.bin` — one `pickle.load`, nothing else —
built ahead of time by:

```bash
pravapis build-artifact          # validates data/MANIFEST's files against their
                                  # JSON Schemas, then writes data/pravapis-<hash>.bin
```

`<data-hash>` is `pravapis.dataversion.compute_data_hash()`: the same sha256, computed
the same way, that `GET /v1/version` reports as `data_hash` — the artifact
deployed and the hash the API claims to be running can never quietly disagree, because
they are the same number by construction (`pravapis.artifact`).

**There is no build step in this deployment**, so the artifact is committed to git like
the GrammarDB stress tables already were — regenerate and recommit it after any change
to a `data/MANIFEST`-listed file:

```bash
rm data/pravapis-*.bin && pravapis build-artifact   # old hash gone, new one written
git add data/pravapis-*.bin
```

`tests/test_artifact.py::test_committed_artifact_is_not_stale` catches a forgotten
rebuild the same way `test_conformance.py::test_corpus_is_not_stale` catches a
forgotten `export-conformance`. A file the manifest does not list changes nothing —
`test_a_stray_file_outside_the_manifest_does_not_change_the_artifact` builds twice,
once with an extra unlisted file in `data/lexicon/stems/`, and asserts the two
artifacts are byte-for-byte identical.

Two things needed fixing to make "byte-for-byte identical" true across separate
process runs at all: `marisa_trie`'s own pickle support and `regex.Pattern`'s (for
patterns built from a string alternation, e.g. `StemIndex`'s unanchored-stem regex)
are each internally non-deterministic between processes even for identical content —
confirmed empirically, not assumed. `Lexicon`, `StressTable`, `MentSuffix` and
`StemIndex` now pickle their tries via `.tobytes()`/`.frombytes()` (marisa\_trie's own
*native* serialization, which **is** stable) instead of directly; `Rule` pickles a
compiled pattern as `(source, flags)` and recompiles on load. A third, real source of
non-determinism — at least one hash-order-sensitive `frozenset` still reachable from
the object graph — needed `PYTHONHASHSEED` pinned too, so `build_artifact()` re-execs
itself once with it fixed rather than leaving that to chance.

Not bundled: transliteration schemes and the (off-by-default) disambiguation
classifier — both still parse YAML lazily on first use. See `pravapis/artifact.py`'s
module docstring.

**Measured** (local; `scripts/measure_artifact_perf.py`, not Vercel's own network and
container overhead — this is the ceiling `pravapis build-artifact` controls, not a
deployed-p95 promise):

| | p50 | p95 | max | target | |
|---|---|---|---|---|---|
| cold start (fresh process, import → ready) | 0.236s | **0.239s** | 0.247s | p95 < 1.5s | met |
| warm (1k-char input, through `pravapis.webapi.handle`) | 3.41ms | **3.99ms** | 5.20ms | p95 < 50ms | met |

Payload: code plus the 700 KB artifact, well under 1 MB; dependencies 17.7 MB installed.
The raw sources (`rules/*.yaml`, `lexicon/*.tsv`, the uncompiled stress/-мент tables)
still ship in the bundle too — nothing in the hot path reads them, but nothing excludes
them yet either; see `vercel.json`.

### Vercel dashboard steps

1. Push this repository to GitHub (`origin` is already `sewstie/pravapis`).
2. **Add New… → Project → Import** the repository.
3. **Framework Preset: Other.** Root Directory: the repository root. Leave Build Command and
   Install Command empty/default. Output Directory is set to `public` by `vercel.json`.
4. No environment variables are needed. Deploy.
5. Open the build log and check the Python install step lists only the four packages from
   `requirements.txt`. The repository also has `pyproject.toml` and `uv.lock`; if Vercel
   installs from those instead, the function still works but also pulls FastAPI, Typer and
   Rich. If that happens, tell me and the dev dependencies can be moved out of the way.
6. Check it: open the deployment URL for the demo, and
   `curl -X POST https://<deployment>/api/convert -H 'Content-Type: application/json' -d '{"text":"снег"}'`
   should return `{"result": "сьнег", …}`.
7. Optional: **Settings → Domains** to attach a custom domain. The CORS allowlist does not
   depend on the API's own domain.

### Run it locally

```bash
python scripts/serve_local.py --port 3000   # public/ at /, the function at /api/convert
```

`scripts/export_vercel.py` still exists for embedding the function in another repository
(vendored under `api/_pravapis/`); it is not used by the standalone deployment.

### The npm package

`js/` is a from-scratch TypeScript port of the same cascade (tokenizer, rule engine,
lexicon, transliterator), reading the same `data/` files through a build step
(`js/scripts/build-data.ts`) that translates the Python `regex` dialect to JS `RegExp`
and validates every file against the same JSON Schemas. It has no runtime dependencies
and ships three entry points — `.` (conversion), `./translit`, `./names` (the proper-noun
table, loaded lazily since most conversions never touch one) — each built as ESM and
CJS with bundled `.d.ts`. `npm test` runs `conformance/cases.jsonl` against it; the one
documented gap is the missing GrammarDB stress table (~680KB gzipped were it included),
tracked case-by-case in `js/scripts/known-gaps.json` rather than silently accepted.

## Layout

```
data/schemas/    JSON Schemas — the normative spec for every data format
data/VERSION     the data package's own semver (see data/VERSIONING.md)
conformance/     cases.jsonl, known_failures.jsonl, manifest.json — the cross-language
                 contract, generated by `pravapis export-conformance`
data/rules/      YAML rules (palatalization, loanwords, morphology), each rule cited
data/translit/   Łacinka + official-2007 scheme tables, with inline tests
data/chars/      the alphabet, apostrophe-class and homoglyph tables every tokenizer/
                 sanitizer implementation reads (see data/schemas/)
data/lexicon/    TSV sources → data/lexicon.marisa
data/lexicon/stems/  stem etymology inventory (loan / native) gating the loanword
                 rules. ONLY stems.tsv: the directory is globbed, so a file without the
                 `#!schema` declaration is ignored rather than loaded as inventory
data/corpora/    parallel.tsv (aligned be ↔ be-tarask sentence pairs, for recall),
                 frequency_be.tsv (Narkamaŭka word-form frequency, for coverage and for
                 ranking stem candidates) and frequency_tarask.tsv (the same from
                 be-tarask, which is what says whether a candidate stem would corrupt
                 real words) — all generated, all measurement-only, never read by
                 lexicon or stem building
data/review/     stem_candidates.tsv — mined proposals awaiting a human. Deliberately
                 not under data/lexicon/stems/, which is loaded
data/eval/       gold.tsv (held out, with provenance and an origin header),
                 negative.tsv (words that must not change — the precision gate),
                 roundtrip_corpus.txt, roundtrip_regressions.tsv, ambiguous.tsv
data/eval/tarask/  genuine Taraškievica from be-tarask (CC BY-SA 4.0): corpus.tsv,
                 audit.tsv, gold_t2n.tsv — independent T → N evaluation.
                 REVIEW.md is the handoff: what is unreviewed and how to check it
src/pravapis/    normalize, tokenize, rules/, lexicon/, translit/, stress, pipeline,
                 metrics, webapi, api/ (FastAPI), cli,
                 dataspec (schema validation + data version), conformance (corpus export),
                 disambiguate/ (experimental, off by default)
js/              the npm package: src/ (the port), scripts/ (data build + conformance
                 test runner), dist/ (built, gitignored)
api/             Vercel function (convert.py)
public/          the conversion form served at /
data/stress/     GrammarDB first-syllable stress tables (CC BY-SA 4.0)
tests/           pytest + hypothesis
benchmarks/      pytest-benchmark
```
