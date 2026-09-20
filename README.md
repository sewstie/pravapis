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
| **Change accuracy** (words that should change) | **99.2%** (606/611) | 0.0% | 99.0%\* (605/611) | 0.0% |
| False-positive rate (words that should not change) | 0.0% (0/3,376) | 0.0% | 0.0%\* (0/3,376) | 0.0% |
| Word accuracy | 99.9% | 84.7% | 99.9%\* | 84.7% |
| Word round trip (there and back) | 99.95% | 100% | 99.95% | 100% |

**\* The T → N column is self-consistency, not accuracy — and it overstates by 7 points.** `gold.tsv` declares
`# origin: narkamauka`: its Narkamaŭka side is the original and its Taraškievica side was
written from it by applying the 2005 norm. Scoring T → N on it therefore asks whether the
converter can undo a transformation produced by the same reading of the norm it
implements. That is worth knowing and it is not nothing — but it is not evidence that
T → N is *right*, and the two columns landing on an identical 96.7% with identical
denominators is the tell. `pravapis eval` prints this caveat itself, from the file's own
header, so a future edit cannot quietly drop it.

Measured against **genuine Taraškievica** instead — 150 hand-reviewed sentences from
be-tarask.wikipedia.org that nobody derived from Narkamaŭka — T → N change accuracy is
**92.6%**, not 99.0%. That gap is the entire reason `data/eval/tarask/` exists. See
[Independent T → N](#independent-t--n).

The directions did diverge before Phase A: the reverse loanword rules were inverse
transducers guessing which `ь` to remove (`балькон → балкон` must drop one,
`лякальна → лакальна` must not, and the string does not say which), which cost them
recall of 0.22 and 0.36. T → N is now a stem substitution derived from the forward
inventory, so it cannot disagree with it, and its recall is 1.0.

The full scored set (637 sentences; `converter_checked` rows included, `uncertain` excluded) is
within 0.5 points of these on every metric. Throughput: **0.6–1.0 MB/s**.

Most of the gap from 96.7% closed by adding the stems the errors named — the remaining
misses are a grammatical-gender change (`Аналіз паказаў → Аналіза паказала`), a genitive
that changes ending (`Мінска → Менску`), and `не → ня` where GrammarDB does not know the
next word's stress. None of those is a missing rule; they need a morphological layer that
re-inflects, which is written up as a gap in `data/NORMS.md`.

CI fails if the false-positive rate on the trusted subset rises above zero, in either
direction. That gate is what lets the stem inventory grow without the headline number
quietly rotting.

не → ня and без → бяз use GrammarDB stress marks (`data/stress/`, CC BY-SA 4.0) to decide
whether the next word is stressed on its first syllable.

Where the codification allows more than one form, the converter leaves the input alone
(`data/NORMS.md`, "Policy: optional forms"): Фёдар stays Фёдар, the conjunction і stays і.
`--aggressive` on the CLI or `"aggressive": true` in the API also applies those optional
rewrites (Фёдар → Хведар, і → й after a vowel).

**The letter ґ is never produced.** Збор 2005 зноска 55 licenses it in a list of
borrowings and the alphabet marks it *факультатыўна* — optional — so both spellings are
correct and the choice is the project's. It writes г everywhere, and normalises a ґ
arriving in input back to г. The citation is kept in `data/NORMS.md` so the decision can
be reversed by adding stems back rather than re-researched.

A native reviewer has not yet read any of it. `scripts/review_packet.py` collects every
question that needs one — the changes where the audit and the gold contradict each other,
the stems held back for want of a source, and the places two cited sections point
different ways — into `data/eval/tarask/review-packet.md`, answerable without reading the
code.

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

## Independent T → N

Everything above comes from one gold set whose Taraškievica side is derived. To measure
T → N on text a Taraškievica writer actually produced, `data/eval/tarask/` holds
sentences sampled from be-tarask.wikipedia.org, each with its article and revision id.
Only sentences carrying a Taraškievica marker are kept — an assimilative `ь`, a loan
`э`/`ы`, a `ґ` — because a sentence that reads identically in both orthographies would
pad the denominator with words that cannot change either way.

```bash
python scripts/fetch_tarask_corpus.py --sentences 400     # 437 sentences, 73 articles
pravapis audit data/eval/tarask/corpus.tsv --to narkamauka     --out data/eval/tarask/audit.tsv
```

**Precision audit.** The converter changes 634 tokens across those sentences, which
collapse to **431 distinct changes** — one row per `(source, target, rule)`, ranked by
frequency. That is the unit a human can judge; judging tokens would mean reading the
same change hundreds of times. Mark each `ok` / `wrong` / `unsure`, and precision is the
token-weighted `ok / (ok + wrong)`, reported beside the share still unreviewed. Re-running
the audit keeps verdicts already recorded, re-counts against the current converter, and
drops changes it no longer makes.

**Reviewed in full: 439 distinct changes, all judged `ok` — precision 100%.** `data/eval/tarask/REVIEW.md` has the
method; `pravapis audit --rule ... --sample N` and `--mark` are what made it an evening
rather than 438 separate judgements. `pravapis audit` reports precision as *unknown* rather
than 0% or 100%, and the CI gate is inert until there are verdicts to hold.

**Recall** needs gold, so `scripts/propose_gold_t2n.py` drafted the Narkamaŭka side of
150 corpus sentences into `data/eval/tarask/gold_t2n.tsv` (`# origin: taraskievica` — the
mirror of `gold.tsv`). Drafts carry provenance `proposed` and are **never scored**: a
converter proposal scored against the converter returns 100% by construction. A human
corrected and promoted all 150 to `hand_written`, which is what makes the figure below
mean anything.

| T → N, 150 hand-reviewed be-tarask sentences | converter | baseline |
|---|---|---|
| **Change accuracy** (258 words that should change) | **92.6%** | 0.0% |
| False-positive rate (2,173 that should not) | 0.3% (6) | 0.0% |
| Word accuracy (2,431 words) | 99.0% | 89.4% |
| Sentence accuracy | 86.7% | 18.0% |

All six false positives come from four changes — `сымбалізм → сімвалізм`,
`сымбалізуе → сімвалізуе`, `максымум → максімум`, `спэктаклі → спектаклі` — that the
**audit marks `ok` and the gold marks as words that should not change**. The two files
disagree, so at least one is wrong, and both were written by the same reviewer. They are
left contradicting each other rather than silently reconciled in the converter's favour:
correcting the yardstick to agree with the tool is how a measurement stops meaning
anything. `scripts/check_gold_t2n.py` lists the rows involved.

What the remaining errors are, honestly: three are words the gold and the converter still
disagree about, and most of the rest are **lexical, not orthographic** — `зьвязу → саюзу`,
`нямецкіх → германскіх`, `альбо → або`, `інсцэнізацыі → пастаноўкі`. Taraškievica prefers
different *words*, not just different spellings, and a word-level orthography converter
has nothing to say about that. It is a distinct gap from the morphological one.

Two checks keep this file honest: `scripts/check_gold_t2n.py` runs the Narkamaŭka column
back through the converter and reports any row it would change again (a row is not
finished if its own Narkamaŭka side still reads as Taraškievica), and
`scripts/triage_gold_t2n.py` cross-references drafts against the audit so review time goes
to the rows that need it.

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
are in [`data/TRANSLIT.md`](data/TRANSLIT.md).

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
pravapis audit data/eval/tarask/corpus.tsv --to narkamauka --out audit.tsv
pravapis audit data/eval/tarask/corpus.tsv --rule palat.unassim --sample 15
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
data/eval/       gold.tsv (held out, with provenance and an origin header),
                 roundtrip_corpus.txt, ambiguous.tsv (classifier training)
data/eval/tarask/  genuine Taraškievica from be-tarask (CC BY-SA 4.0): corpus.tsv,
                 audit.tsv, gold_t2n.tsv — independent T → N evaluation.
                 REVIEW.md is the handoff: what is unreviewed and how to check it
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
