# belnorm

Bidirectional Belarusian orthography converter — **Narkamaŭka ↔ Taraškievica** — built as a
cascade of a lexicon and a declarative rule engine. Ships as a Python library, a CLI and a
FastAPI service.

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
| 4 | Passthrough | `unknown` | most words are spelled the same in both |

The lexicon comes before the rules because loanwords are exactly what the rules get wrong.
Words that neither stage resolves are left unchanged: leaving a word alone is better than
getting it wrong.

An experimental classifier exists in `src/belnorm/disambiguate/` but is **off by default** and
not part of the architecture above; see [Why the classifier was removed](#why-the-classifier-was-removed).

Rules live in `data/rules/*.yaml` and include inline positive/negative test cases. The test
suite runs those cases and checks that the YAML agrees with the pure-Python reference
implementations in `src/belnorm/rules/`.

## Results

Measured with `belnorm eval data/eval/gold.tsv --trusted` and `belnorm bench --size 10mb` on
a desktop Windows 11 machine, single process, classifier off. Every number sits next to the
**do-nothing baseline** (return the input unchanged).

The trusted subset is the 577 `hand_written` gold sentences (4,031 words, 620 of which should
change): rows never adjusted after seeing converter output.

| | N → T | baseline | T → N | baseline |
|---|---|---|---|---|
| **Change accuracy** (words that should change) | **95.3%** (591/620) | 0.0% | **96.0%** (595/620) | 0.0% |
| False-positive rate (words that should not change) | 0.03% (1/3,411) | 0.0% | 0.0% (0/3,411) | 0.0% |
| Word accuracy | 99.3% | 84.6% | 99.4% | 84.6% |
| Word round trip (there and back) | 99.95% | 100% | 99.83% | 100% |

The full scored set (634 sentences; `converter_checked` rows included, `uncertain` excluded) is
within 0.3 points of these on every metric. Coverage on it: lexicon 1.6%, rules 13.8%,
identity 0.7%, unchanged 83.9%. Throughput: **1.00 MB/s** (~77k words/s).

Caveats:

- **The gold Taraškievica is not native-reviewed.** It was written by a human reviewer from Klasyčny
  pravapis (2005), sentence by sentence, as word edits on Narkamaŭka text from the Paznaj site.
  Treat the numbers as "agrees with a careful reading of the norm", not as ground truth.
- 620 changed words is still small: one word moves change accuracy by 0.16 points.
- Most words are spelled the same in both orthographies, which is why word accuracy starts at
  84.6% for doing nothing and why change accuracy is the headline.
- Remaining misses are mostly loanwords the rules do not cover (`версія → вэрсія`,
  `аперацый → апэрацый`), `не → ня` before stressed words the stress heuristic does not know,
  and one grammatical-gender change (`Аналіз паказаў → Аналіза паказала`) that a word-level
  converter cannot make.

## Why the classifier was removed

The cascade used to have a fourth stage: a logistic-regression classifier on character n-grams,
consulted for words that matched an "ambiguity trigger" (hard л after a consonant, е after a
consonant, `сі`/`зі`) and that neither the lexicon nor the rules changed. It is now off by
default. `Config.default()` never loads it, and `Method.MODEL` cannot be reached unless a config
file names a model explicitly and the `[ml]` extra is installed.

Measured on the gold set (scored rows, N → T, the only direction it ran in):

- It changed **58 words** and got **12 of them right (20.7%)**.
- **42 were false positives** — native words that should not change, e.g.
  `беларуская → бэларуская`, `кладзіце → клядзіце`, `лаўровы → ляўровы`,
  `менавіта → мэнавіта`, `найстаражытнейшых → найстаражытнэйшых`, `паклон → паклён`.
- 4 were loans it changed the wrong way (`сімвалізуе → сымвалізуе`, not `сымбалізуе`).
  Confidence was no guard: `серавадароду → сэравадароду` scored 0.99.
- Net effect of turning it on: change accuracy 95.2% → 96.8% (+12 words), but false-positive
  rate 0.03% → 1.1% (+42 words) and word accuracy 99.2% → 98.5%. Word round trip fell from
  99.96% to 98.67%, and every remaining round-trip failure on the mining corpus
  (93 of 7,809 words) was the classifier's.

**Diagnosis.** The rules it was meant to arbitrate — loanword л → ль, е → э, і → ы — apply to
*borrowings* and never to native vocabulary. Whether a word is borrowed is a fact about its
etymology, not its spelling: native `кладзіце` and borrowed `клас` (Taraškievica `кляса`) share the `кла` n-gram,
native `беларуская` and borrowed `бензін` (Taraškievica `бэнзін`) share `бе`. Character n-grams cannot encode that
distinction, so the model learned "this letter pattern often takes the loan spelling" and
applied loanword rules to native words.

**The correct fix is data, not a better model:** a `native` / `loan` flag on lexicon entries,
which the л/э/ы loanword rules consult before firing.

## Install

```bash
uv sync                  # core: rules + lexicon
uv sync --extra ml       # + experimental classifier, opt-in only (pip install belnorm[ml])
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
belnorm eval data/eval/gold.tsv --json eval.json   # skips uncertain rows, compares subsets
belnorm eval data/eval/gold.tsv --trusted          # hand_written rows only
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

The lexicon and rules are loaded once in the FastAPI lifespan handler.

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
data/eval/       gold.tsv (held out, with provenance), roundtrip_corpus.txt,
                 ambiguous.tsv (experimental classifier training)
src/belnorm/     normalize, tokenize, rules/, lexicon/, pipeline, metrics, api/, cli
                 disambiguate/ (experimental, off by default)
tests/           pytest + hypothesis
benchmarks/      pytest-benchmark
```

## License

MIT
