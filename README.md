# pravapis

Bidirectional Belarusian orthography converter — **Narkamaŭka ↔ Taraškievica** — built as a
cascade of a lexicon and a declarative rule engine, with Cyrillic ↔ Latin transliteration
(Łacinka and the 2007 national romanisation). Ships as a Python library, a CLI and a
FastAPI service.

```
$ pravapis convert "Снег і свет у Еўропе, план сістэмы" --to taraskievica
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

The loanword rules at stage 3 are **gated on etymology**, which is a data file rather
than a pattern: `data/lexicon/stems/stems.tsv` says whether a stem is a borrowing, and
soft л / і → ы / е → э fire only inside a stem classed `loan`. Longest match wins, so a
false friend is a native stem one character longer than the loan stem it must beat
(`класц` over `клас`), and no rule carries a lookahead. See
[Etymology is data](data/NORMS.md).

The lexicon comes before the rules because loanwords are exactly what the rules get wrong.
Words that neither stage resolves are left unchanged: leaving a word alone is better than
getting it wrong.

An experimental classifier exists in `src/pravapis/disambiguate/` but is **off by default** and
not part of the architecture above; see [Why the classifier was removed](#why-the-classifier-was-removed).

Rules live in `data/rules/*.yaml` and include inline positive/negative test cases. The test
suite runs those cases and checks that the YAML agrees with the pure-Python reference
implementations in `src/pravapis/rules/`.

## Results

Measured with `pravapis eval data/eval/gold.tsv --trusted` and `pravapis bench --size 10mb` on
a desktop Windows 11 machine, single process, classifier off. Every number sits next to the
**do-nothing baseline** (return the input unchanged).

The trusted subset is the 571 `hand_written` gold sentences (3,987 words, 611 of which should
change): rows never adjusted after seeing converter output.

| | N → T | baseline | T → N | baseline |
|---|---|---|---|---|
| **Change accuracy** (words that should change) | **96.7%** (591/611) | 0.0% | **96.7%** (591/611) | 0.0% |
| False-positive rate (words that should not change) | 0.0% (0/3,376) | 0.0% | 0.0% (0/3,376) | 0.0% |
| Word accuracy | 99.5% | 84.7% | 99.5% | 84.7% |
| Word round trip (there and back) | 99.95% | 100% | 99.95% | 100% |

The two directions are now symmetric. They were not before: the reverse loanword rules
were inverse transducers guessing which `ь` to remove (`балькон → балкон` must drop one,
`лякальна → лакальна` must not, and the string does not say which), which cost them
recall of 0.22 and 0.36. T → N is now a stem substitution derived from the forward
inventory, so it cannot disagree with it, and its recall is 1.0.

The full scored set (637 sentences; `converter_checked` rows included, `uncertain` excluded) is
within 0.4 points of these on every metric. Coverage on it: lexicon 1.6%, rules 14.0%,
identity 0.7%, unchanged 83.8%. Throughput: **0.6–1.0 MB/s**.

CI fails if the false-positive rate on the trusted subset rises above zero, in either
direction. That gate is what lets the stem inventory grow without the headline number
quietly rotting.

не → ня and без → бяз use GrammarDB stress marks (`data/stress/`, CC BY-SA 4.0) to decide
whether the next word is stressed on its first syllable.

Where the codification allows more than one form, the converter leaves the input alone
(`data/NORMS.md`, "Policy: optional forms"): Фёдар stays Фёдар, the conjunction і stays і.
`--aggressive` on the CLI or `"aggressive": true` in the API also applies those optional
rewrites (Фёдар → Хведар, і → й after a vowel).

Caveats:

- **The gold Taraškievica is not native-reviewed.** It was written by a human reviewer from Klasyčny
  pravapis (2005), sentence by sentence, as word edits on Narkamaŭka text from the Paznaj site.
  Treat the numbers as "agrees with a careful reading of the norm", not as ground truth.
- 611 changed words is still small: one word moves change accuracy by 0.16 points.
- Most words are spelled the same in both orthographies, which is why word accuracy starts at
  84.7% for doing nothing and why change accuracy is the headline.
- Remaining misses are loanwords whose stems are not in the inventory yet (`Лабірынт →
  Лябірынт`, `Семантыка → Сэмантыка`, `сертыфікаваным → сэртыфікаваным`), `не → ня` before
  stressed words the stress heuristic does not know, irregular pairs no alternation derives
  (`сімвал → сымбаль`), and one grammatical-gender change (`Аналіз паказаў → Аналіза
  паказала`) that a word-level converter cannot make. The first class is the one that
  shrinks by adding data — see `scripts/mine_loan_stems.py`.

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

**The correct fix is data, not a better model:** a `native` / `loan` flag the л/э/ы
loanword rules consult before firing.

**That fix is now implemented**, though not quite where this section originally predicted.
A flag on *lexicon entries* would have done nothing: the cascade stops at the first hit, so
a word the lexicon resolves never reaches the rules. The flag has to sit on something the
rules can match beyond exact word forms — a stem. `data/lexicon/stems/stems.tsv` carries
one row per stem with its class, the alternations it licenses, a citation and a provenance
tier, and the rules consult it. `беларуская`, `кладзіце`, `лаўровы`, `менавіта` and
`паклон` — five of the classifier's false positives — are left alone because their stems
are classed `native`, and `версія → вэрсія` now works because `версі` is classed `loan`.

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

`official` is forward-only on purpose: it does not write assimilative softness, so
reading it back would be a guess about something the source never recorded, and this
project does not guess — `Transliterator.load(reverse=True)` raises for it.

Schemes are YAML tables with inline tests (`data/translit/*.yaml`), read by a
longest-match single-pass transducer. Conditions are a closed vocabulary
(`after_vowel`, `after_consonant`, `after_l`, …) rather than regex, so a scheme can be
checked against a published table by someone who does not read Python. Every letter of
the alphabet must be covered, or the tests fail. Sources and the two known limitations
are in [`data/TRANSLIT.md`](data/TRANSLIT.md).

Measured: Łacinka round-trips **≥ 99.9%** of the Taraškievica words the project ships
(lexicon targets, gold set and mining corpus). The residue is one genuine collision —
Cyrillic `й` + vowel and the iotated vowel are the same Łacinka string, so
`найадметнейшых` and `наядметнейшых` both give `najadmietniejšych` — plus a bare `ь`
after a consonant with no soft Latin counterpart, which is reported as `unresolved`
rather than silently dropped.

## Install

```bash
uv sync                  # core: rules + lexicon
uv sync --extra ml       # + experimental classifier, opt-in only (pip install pravapis[ml])
```

## Library

```python
from pravapis import Converter, Orthography, Script, convert

convert("Не быў без мяне", Orthography.TARASKIEVICA)   # 'Ня быў безь мяне'

conv = Converter.from_config()          # loads data/ once; reuse it
result = conv.convert("сістэма", Orthography.TARASKIEVICA)
result.text, result.stats, result.conversions

conv.render("снег", Script.LACINKA)                     # 'śnieh'  (converts first)
conv.render("снег", Script.LACINKA, convert=False)      # 'snieh'
conv.render("снег", Script.OFFICIAL)                    # 'snieh'
conv.read_script("śnieh", Script.LACINKA)               # 'сьнег'
```

## CLI

```bash
pravapis convert "снег" --to taraskievica
pravapis convert --file in.txt --out out.txt --to narkamauka
cat in.txt | pravapis convert --to taraskievica
pravapis translit "снег" --to lacinka                # śnieh (converts first)
pravapis translit "снег" --to lacinka --no-convert   # snieh
pravapis translit "снег" --to official               # snieh
pravapis translit "śnieh" --from lacinka             # сьнег
pravapis explain "сімвал" --to taraskievica
pravapis build-lexicon data/lexicon/ --out data/lexicon.marisa
pravapis eval data/eval/gold.tsv --json eval.json   # skips uncertain rows, compares subsets
pravapis eval data/eval/gold.tsv --trusted          # hand_written rows only
pravapis bench --size 10mb
pravapis serve
```

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/convert` | `{"text", "direction", "explain"}` → converted text + stats |
| `POST` | `/v1/transliterate` | `{"text", "script", "from_script", "convert"}` → Latin or Cyrillic |
| `POST` | `/v1/convert/batch` | Up to 100 strings |
| `GET` | `/v1/lexicon/{word}` | Lexicon lookup + which rules would fire |
| `GET` | `/v1/stats` | Lexicon size, rule count, model version |
| `GET` | `/health` | Liveness |

The lexicon and rules are loaded once in the FastAPI lifespan handler.

```bash
docker build -t pravapis .
docker run -p 8000:8000 pravapis
curl -X POST localhost:8000/v1/convert -H 'content-type: application/json' \
     -d '{"text": "план", "direction": "taraskievica"}'
```

Set `PRAVAPIS_DATA_DIR` to point at a different `data/` directory.

## Serverless deployment (Vercel)

This repository deploys as its own Vercel project: a demo page at `/` and a Python
function at `/api/convert`. No FastAPI, no build step.

| File | Role |
|---|---|
| `api/convert.py` | Vercel Python function; thin `BaseHTTPRequestHandler` over `pravapis.webapi` |
| `src/pravapis/webapi.py` | validation, CORS, JSON shapes (stdlib + the converter only) |
| `requirements.txt` | runtime deps for the function: regex, marisa-trie, PyYAML, pydantic |
| `vercel.json` | static output from `public/`; tests, benchmarks, scripts, `data/eval` excluded from the function bundle |
| `public/index.html` | the page at `/`: a plain form, single file, no framework |

`POST /api/convert` takes `{"text", "direction", "explain"}` — plus `"script"`
(`lacinka` / `official`), `"from_script"` and `"convert"` for transliteration — and
returns `{"result", "direction", "script", "stats"}`, plus `segments` (every word with its method, rule id and rule trace)
when `explain` is true. The page itself sends only `text` and `direction`. Cross-origin calls are allowed from `https://paznaj.by`,
`https://www.paznaj.by` and `http://localhost` / `http://127.0.0.1` on any port; `OPTIONS`
preflight is answered with 204.

Payload: code, rules, lexicon TSVs and the 626 KB stress table, under 1 MB; dependencies
17.7 MB installed. The compiled `data/lexicon.marisa` is git-ignored, so a deployment builds
the lexicon from `data/lexicon/*.tsv` at cold start (a few milliseconds at its current size).

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

## Layout

```
data/rules/      YAML rules (palatalization, loanwords, morphology)
data/translit/   Łacinka + official-2007 scheme tables, with inline tests
data/lexicon/    TSV sources → data/lexicon.marisa
data/lexicon/stems/  stem etymology inventory (loan / native) gating the loanword rules
data/eval/       gold.tsv (held out, with provenance), roundtrip_corpus.txt,
                 ambiguous.tsv (experimental classifier training)
src/pravapis/    normalize, tokenize, rules/, lexicon/, translit/, stress, pipeline,
                 metrics, webapi, api/ (FastAPI), cli,
                 disambiguate/ (experimental, off by default)
api/             Vercel function (convert.py)
public/          the conversion form served at /
data/stress/     GrammarDB first-syllable stress tables (CC BY-SA 4.0)
tests/           pytest + hypothesis
benchmarks/      pytest-benchmark
```

## License

MIT
