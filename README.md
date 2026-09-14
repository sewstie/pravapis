# belnorm

Bidirectional Belarusian orthography converter — **Narkamaŭka ↔ Taraškievica** — built as a
cascade of a lexicon, a declarative rule engine and a character n-gram classifier. Ships as a
Python library, a CLI and a FastAPI service.

```
$ belnorm convert "Снег і свет у Еўропе, план сістэмы" --to taraskievica
Сьнег і сьвет у Эўропе, плян сыстэмы
```

## How it works

Each word goes through a cascade. The first stage that resolves it wins:

| # | Stage | Method | Example |
|---|---|---|---|
| 1 | Never-changes set | `identity` | `і`, `у` |
| 2 | Lexicon (marisa-trie, case-folded, case re-applied) | `lexicon` | `сімвал → сымбаль` |
| 3 | YAML rule engine (regex, priority-ordered, fixpoint for chained softness) | `rule` | `свіння → сьвіньня` |
| 4 | Classifier (TF-IDF char n-grams + logistic regression), only on ambiguity triggers, only above 0.75 confidence | `model` | context-dependent loans |
| 5 | Passthrough | `unknown` | most words are spelled the same in both |

The lexicon comes before the rules because loanwords are exactly what the rules get wrong. Below
the confidence threshold the model returns the input unchanged, because leaving a word alone is
better than getting it wrong.

Rules live in `data/rules/*.yaml` and include inline positive/negative test cases. The test
suite runs those cases and checks that the YAML agrees with the pure-Python reference
implementations in `src/belnorm/rules/`.

## Results

Measured with `belnorm eval data/eval/gold.tsv` (full report in `eval.json`) and
`belnorm bench --size 5mb` on a desktop Windows 11 machine, single process:

| | N → T | T → N |
|---|---|---|
| Word accuracy | **99.6%** | **97.8%** |
| Sentence accuracy | 98.7% | 93.7% |
| Round trip (N→T→N) | 94.9% | 94.9% |
| Resolved by lexicon / rule / model | 13.8% / 20.3% / 1.3% | 13.8% / 19.8% / 0% |
| Unchanged by design (identity + passthrough) | 64.6% | 66.4% |

Throughput: **0.66 MB/s** (~55k words/s).

These numbers come with caveats:

- The gold set is small: 79 held-out sentence pairs, 232 words. Treat the accuracy numbers as a
  regression check, not a benchmark.
- About two-thirds of Belarusian words are spelled the same in both orthographies. Most of the
  accuracy comes from leaving those alone, which is why the per-method split is shown.
- The classifier resolves 3 of 232 words (1.3%). Rules and the lexicon do most of the work.
- Remaining errors are loanwords missing from the reverse lexicon (`Лябірынт → Лабірынт`) and
  grammatical-gender changes that carry into verb agreement (`Аналіз паказаў → Аналіза паказала`),
  which a word-level converter can't handle.

## Install

```bash
uv sync                  # core: rules + lexicon
uv sync --extra ml       # + scikit-learn classifier  (pip install belnorm[ml])
```

## Library

```python
from belnorm import Converter, Orthography, convert

convert("Не быў без мяне", Orthography.TARASKIEVICA)   # 'Ня быў бязь мяне'

conv = Converter.from_config()          # loads data/ once; reuse it
result = conv.convert("сістэма", Orthography.TARASKIEVICA)
result.text, result.stats, result.conversions
```

## CLI

```bash
belnorm convert "снег" --to taraskievica
belnorm convert --file in.txt --out out.txt --to narkamauka
cat in.txt | belnorm convert --to taraskievica
belnorm explain "сімвал" --to taraskievica
belnorm build-lexicon data/lexicon/ --out data/lexicon.marisa
belnorm train data/eval/ambiguous.tsv --out data/models/disambig.joblib
belnorm eval data/eval/gold.tsv --json eval.json
belnorm bench --size 10mb
belnorm serve
```

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/convert` | `{"text", "direction", "explain"}` → converted text + stats |
| `POST` | `/v1/convert/batch` | Up to 100 strings |
| `GET` | `/v1/lexicon/{word}` | Lexicon lookup + which rules would fire |
| `GET` | `/v1/stats` | Lexicon size, rule count, model version |
| `GET` | `/health` | Liveness |

The lexicon and model are loaded once in the FastAPI lifespan handler. If the model is missing,
the service keeps running without it.

```bash
docker build -t belnorm .
docker run -p 8000:8000 belnorm
curl -X POST localhost:8000/v1/convert -H 'content-type: application/json' \
     -d '{"text": "план", "direction": "taraskievica"}'
```

Set `BELNORM_DATA_DIR` to point at a different `data/` directory.

## Development

```bash
uv run pytest            # unit, table-driven, hypothesis property tests, API
uv run ruff check . && uv run ruff format --check .
uv run mypy              # --strict on src/
```

Property tests cover the invariants that matter most: tokenizing is lossless, `sanitize` is
idempotent, the softness layer round-trips N→T→N, conversion never changes non-word tokens,
and converting already-converted text is a no-op. For example, they found that dropping a soft
geminate's `ь` before the assimilative `ь` to its left broke the round trip
(`зллю → зьльлю → зьллю`).

## Layout

```
data/rules/      YAML rules (palatalization, loanwords, morphology)
data/lexicon/    TSV sources → data/lexicon.marisa
data/eval/       gold.tsv (held out), ambiguous.tsv (classifier training)
src/belnorm/     normalize, tokenize, rules/, lexicon/, disambiguate/, pipeline, metrics, api/, cli
tests/           pytest + hypothesis
benchmarks/      pytest-benchmark
```

## License

MIT
