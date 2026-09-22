# Contributing

## Dev install

```bash
uv sync                  # core: rules + lexicon
uv sync --extra ml       # + experimental classifier, opt-in only (pip install pravapis[ml])
```

## Development

```bash
uv run pytest            # unit, table-driven, hypothesis property tests, API
uv run ruff check . && uv run ruff format --check .
uv run mypy              # --strict on src/
```

Property tests cover the invariants that matter most: tokenizing is lossless (on Latin
output too), `sanitize` is idempotent per script, the softness layer round-trips N→T→N,
Łacinka round-trips Cyrillic→Latin→Cyrillic over the whole shipped corpus, conversion
never changes non-word tokens, and converting already-converted text is a no-op. For example, they found that dropping a soft
geminate's `ь` before the assimilative `ь` to its left broke the round trip
(`зллю → зьльлю → зьллю`).

Before sending a change, also run:

```bash
uv run pravapis validate-data                       # data vs data/schemas/
uv run pravapis export-conformance --check           # fail if the corpus is stale
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for what these actually check and why
both exist alongside the test suite rather than folded into it.

## Growing the lexicon

Mine, screen, decide, then review — in that order, because none of the later steps are
trustworthy without the one before it:

```bash
python scripts/mine_wikidata_labels.py --pages 60000   # → data/review/stem_candidates.tsv
python scripts/recall_curve.py --steps 0,25,50,100,165 # what accepting them would buy
python scripts/build_negative_set.py                   # refresh the precision gate
python scripts/update_baseline.py                      # ratchet the new figures up
python scripts/update_baseline.py --milestone          # ... and read the frozen split
```

[docs/ACCURACY.md](docs/ACCURACY.md) has the full method behind each of these — why
candidates are screened against be-tarask frequency data before ranking, what the three
CI gates catch, and what "worth a review session" means in measured terms.

A promoted stem's `source`/`provenance` columns are also a licensing record — see
[data/LICENSE](data/LICENSE), "When a stem's provenance changes", before committing one.

## The codification itself

```bash
python scripts/fetch_reference.py
```

Git-ignored, copyrighted, fetched and hash-checked — see `data/reference/README.md` for
where it comes from and why it is never committed.

## Local demo / serverless function

```bash
python scripts/serve_local.py --port 3000   # public/ at /, the function at /api/convert
pravapis serve                              # the FastAPI service instead
```

## The npm package

```bash
cd js
npm ci
npm run build-data     # data/ -> src/generated/*.json (gitignored, rebuilt every run)
npm run typecheck
npm test               # replays conformance/cases.jsonl against the JS engine
npm run build          # tsup: ESM + CJS + .d.ts -> dist/
```

`npm run build-data` reads `data/MANIFEST` the same way the Python side does and fails
if the two computed data hashes disagree — see
[docs/ARCHITECTURE.md, "The npm package"](docs/ARCHITECTURE.md#the-npm-package).
