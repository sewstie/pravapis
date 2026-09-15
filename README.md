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

The trusted subset is the 573 `hand_written` gold sentences (3,998 words, 614 of which should
change): rows never adjusted after seeing converter output.

| | N → T | baseline | T → N | baseline |
|---|---|---|---|---|
| **Change accuracy** (words that should change) | **96.1%** (590/614) | 0.0% | **95.9%** (589/614) | 0.0% |
| False-positive rate (words that should not change) | 0.0% (0/3,384) | 0.0% | 0.0% (0/3,384) | 0.0% |
| Word accuracy | 99.4% | 84.6% | 99.4% | 84.6% |
| Word round trip (there and back) | 99.95% | 100% | 99.97% | 100% |

The full scored set (637 sentences; `converter_checked` rows included, `uncertain` excluded) is
within 0.4 points of these on every metric. Coverage on it: lexicon 1.6%, rules 13.8%,
identity 0.7%, unchanged 83.9%. Throughput: **0.98 MB/s** (~75k words/s).

не → ня and без → бяз use GrammarDB stress marks (`data/stress/`, CC BY-SA 4.0) to decide
whether the next word is stressed on its first syllable.

Caveats:

- **The gold Taraškievica is not native-reviewed.** It was written by a human reviewer from Klasyčny
  pravapis (2005), sentence by sentence, as word edits on Narkamaŭka text from the Paznaj site.
  Treat the numbers as "agrees with a careful reading of the norm", not as ground truth.
- 614 changed words is still small: one word moves change accuracy by 0.16 points.
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

convert("Не быў без мяне", Orthography.TARASKIEVICA)   # 'Ня быў безь мяне'

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

## Serverless deployment (Vercel)

This repository deploys as its own Vercel project: a demo page at `/` and a Python
function at `/api/convert`. No FastAPI, no build step.

| File | Role |
|---|---|
| `api/convert.py` | Vercel Python function; thin `BaseHTTPRequestHandler` over `belnorm.webapi` |
| `src/belnorm/webapi.py` | validation, CORS, JSON shapes (stdlib + the converter only) |
| `requirements.txt` | runtime deps for the function: regex, marisa-trie, PyYAML, pydantic |
| `vercel.json` | static output from `public/`; tests, benchmarks, scripts, `data/eval` excluded from the function bundle |
| `public/index.html` | demo page (single file, no framework) |

`POST /api/convert` takes `{"text", "direction", "explain"}` and returns `{"result",
"direction", "stats"}`, plus `segments` (every word with its method, rule id and rule trace)
when `explain` is true. Cross-origin calls are allowed from `https://paznaj.by`,
`https://www.paznaj.by` and `http://localhost` / `http://127.0.0.1` on any port; `OPTIONS`
preflight is answered with 204.

Payload: code, rules, lexicon TSVs and the 626 KB stress table, under 1 MB; dependencies
17.7 MB installed. The compiled `data/lexicon.marisa` is git-ignored, so a deployment builds
the lexicon from `data/lexicon/*.tsv` at cold start (a few milliseconds at its current size).

### Vercel dashboard steps

1. Push this repository to GitHub (it has no remote yet).
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
(vendored under `api/_belnorm/`); it is not used by the standalone deployment.

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
src/belnorm/     normalize, tokenize, rules/, lexicon/, stress, pipeline, metrics, webapi,
                 api/ (FastAPI), cli, disambiguate/ (experimental, off by default)
api/             Vercel function (convert.py)
public/          demo page served at /
data/stress/     GrammarDB first-syllable stress tables (CC BY-SA 4.0)
tests/           pytest + hypothesis
benchmarks/      pytest-benchmark
```

## License

MIT
