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
| **Change accuracy** (words that should change) | **99.0%** | 0.0% | 98.7%\* | 0.0% |
| False-positive rate (words that should not change) | 0.0% (0/3,376) | 0.0% | 0.0%\* (0/3,376) | 0.0% |
| Word accuracy | 99.9% | 84.7% | 99.9%\* | 84.7% |
| Word round trip (there and back) | 99.95% | 100% | 99.95% | 100% |

**\* The T → N column is self-consistency, not accuracy — and it overstates by 5 points.** `gold.tsv` declares
`# origin: narkamauka`: its Narkamaŭka side is the original and its Taraškievica side was
written from it by applying the 2005 norm. Scoring T → N on it therefore asks whether the
converter can undo a transformation produced by the same reading of the norm it
implements. That is worth knowing and it is not nothing — but it is not evidence that
T → N is *right*, and the two columns landing on an identical 96.7% with identical
denominators is the tell. `pravapis eval` prints this caveat itself, from the file's own
header, so a future edit cannot quietly drop it.

Measured against **genuine Taraškievica** instead — 150 sentences from
be-tarask.wikipedia.org that nobody derived from Narkamaŭka — T → N change accuracy is
**98.4%** (245/249). Of the four remaining misses one is a typo in the gold's Narkamaŭka
column (`еўрапйскім`) and one is the §71 genitive, which runs forward only by design. It
read 94.7% until 28 of its 150 rows were found to have drifted from the corpus and were
restored — see
[Independent T → N](#independent-t--n).

The directions did diverge before Phase A: the reverse loanword rules were inverse
transducers guessing which `ь` to remove (`балькон → балкон` must drop one,
`лякальна → лакальна` must not, and the string does not say which), which cost them
recall of 0.22 and 0.36. T → N is now a stem substitution derived from the forward
inventory, so it cannot disagree with it, and its recall is 1.0.

The full scored set (637 sentences; `converter_checked` rows included, `uncertain` excluded) is
within 0.5 points of these on every metric. Throughput: **1.2 MB/s** (~93k words/s).

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

The -мент suffix (дакумент → дакумэнт, дакументацыя → дакумэнтацыя) uses the same
paradigms: the э belongs to the base noun and is inherited by everything derived from it,
even where the stress has moved, so per-form stress is the wrong fact to store.

The genitive plural in -аў is a **whitelist, not a rule** — and not a § either. Збор 2005 is a
spelling code (§1–92) and does not legislate declension; its §80 is the German *ei* rule
(Ляйпцыг, Айнштайн). Taraškievica extends -аў to feminine and neuter nouns in a
vowel — sourced here to the project owner's instruction — but for many words both forms
are permissible — хвілін and
хвілінаў equally — so six nouns where -аў is strongly preferred sit in
`data/lexicon/exceptions.tsv` and everything else is left alone. A table-driven version
built from every GrammarDB noun was tried first and cost 10 false positives to gain 3
words; replacing it with the whitelist also took 752 KiB out of the deployment payload.

§46 gives д + ск → дзк before the adjective suffix (мадрыдскі → мадрыдзкі, гарадскі →
гарадзкі), where Narkamaŭka keeps the root consonant. It applies by the stem's final
consonant, not by whether the word is foreign: бэрлінскі and нью-ёркскі keep their
clusters. And the adjective suffix -ейск- keeps its е whatever the root does (§11б заўвага), so
Эўропа gives эўрапейскі and never эўрапэйскі; a wrongly-spelled эўрапэйскі arriving as
input is normalised back on the way to Narkamaŭka.

Where the codification allows more than one form, the converter leaves the input alone
(`data/NORMS.md`, "Policy: optional forms"): Фёдар stays Фёдар, the conjunction і stays і.
`--aggressive` on the CLI or `"aggressive": true` in the API also applies those optional
rewrites (Фёдар → Хведар, і → й after a vowel, справаў → спраў).

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

## Recall — the changes that did not happen

Everything above measures **precision**: of the changes the converter made, how many
were right. None of it can measure recall, because a miss is a change that should have
happened and there is no list of those. `gold.tsv` cannot supply one — its Taraškievica
side was written by applying the same reading of the norm the converter implements, so a
change the converter does not know about is a change the gold set does not contain
either. The blind spots agree.

`data/corpora/parallel.tsv` supplies one from outside. The same article, written
independently in Narkamaŭka on be.wikipedia.org and in Taraškievica on
be-tarask.wikipedia.org, matched by the Wikidata sitelink that says the two articles are
about the same thing, aligned sentence by sentence and diffed token by token. Each
differing token pair is a change a Taraškievica writer actually made.

```bash
python scripts/fetch_parallel_corpus.py --articles 400   # append to the corpus
pravapis eval --recall --misses misses.tsv               # dev split
pravapis eval --recall --split test                      # frozen; milestones only
```

**5,063 sentence pairs from 895 article pairs.** Split **per article**, never per
sentence: the same loanword recurs all through an article — a biography of Chopin says
Шапэн thirty times — so a sentence split would put the same stem on both sides of the
line and let a stem mined from train score itself on test. The split is written into the
corpus file rather than recomputed, which is what freezes it against a change to the hash
function or the article set.

Sentence pairs are kept on similarity measured **after `pravapis.scope.neutral_fold`**,
which erases exactly the alternations the converter is contracted to make and nothing
else. Scoring raw strings would drop precisely the sentences carrying the most change:
the denser a sentence is in orthography, the less similar its two versions look. The fold
is deliberately not "convert one side and compare", which would keep what the converter
already handles and drop what it does not — the same bias pointing the other way, and
much harder to notice.

### One headline, three declared exclusions

Not every difference between two writers is a change the converter owes. Each attested
difference is sorted into one of four buckets, and **only `in_scope` reaches the
headline**. All four counts are printed: an exclusion nobody can see is indistinguishable
from a filter tuned until the number looked good.

| Bucket | dev | Meaning |
|---|---|---|
| `in_scope` | 58% | differs only by alternations the converter models. **The contract.** |
| `grammatical` | 10% | a case or form ending. Збор 2005 is a spelling code (§1–92) and does not legislate declension, so this is outside the contract by the code's own scope |
| `reference_deviates` | 0% | the be-tarask side contradicts a § of the 2005 code; cited per pattern |
| `not_orthographic` | 33% | the two writers chose different words (`плошчы`/`пляцы`, `годзе`/`року`) |

### The numbers

Every figure carries a Wilson 95% interval. A class of a hundred cases cannot support a
claim narrower than its interval, however precise the point estimate looks.

| split | direction | in-scope recall | precision |
|---|---|---|---|
| dev (1,006 pairs) | N → T | **75.1%** [72.9, 77.1] | 95.2% [93.9, 96.2] |
| dev | T → N | **75.4%** [73.1, 77.3] | 97.1% [96.0, 97.9] |
| test (1,225 pairs, frozen) | N → T | **74.5%** [72.6, 76.4] | 96.0% [94.9, 96.9] |
| test | T → N | **74.8%** [72.9, 76.6] | 97.7% [96.8, 98.3] |

dev and test agree to within a point, which is the main thing a frozen split is for, and
so do the two directions. **Both are measured**, because the package ships both: the only
T → N figure this project used to quote was 98.4% word accuracy on 150 hand-built
sentences, which is a different and much easier question than "of the changes a
Taraškievica writer made, how many can be undone". T → N is the more accurate direction
on precision (97.7% against 96.0%) and has the same stem-inventory gap on recall — it is
mostly removing marks, and removing a mark is easier than knowing where one belongs.

| alternation | dev recall | n | |
|---|---|---|---|
| `soft` — assimilative softness | **98.8%** [98, 99] | 1035/1048 | the rules are done |
| `eu` — еў → эў | 92.9% [69, 99] | 13/14 | small n |
| `i` — і → ы | 69.8% [59, 78] | 60/86 | stem inventory |
| `l` — soft л | 50.4% [42, 59] | 63/125 | stem inventory |
| `other` — mostly у/ў | 42.9% [28, 59] | 15/35 | §18, implemented; see below |
| `e` — е → э | **22.1%** [18, 26] | 94/425 | stem inventory — the gap |

| miss cause | dev n | share |
|---|---|---|
| `stem_absent` | 358 | 82% |
| `rule_silent` | 40 | 9% |
| `rule_wrong` | 30 | 7% |
| `stem_untagged` | 8 | 2% |

**The phonological rules are done and the gap is data.** Softness is at 98.8% over a
thousand cases; 82% of every remaining miss is a stem that is simply absent
(`імператара → імпэратара`, `Шапена → Шапэна`). That is a data problem with a known
procedure, not a rule to think harder about.

**A missing stem is a precision problem too, not only a recall one.** With no stem,
`Снейдэр` keeps its е, the н after it reads as soft, and the softness rule fires:
`Сьнейдэр`, where Taraškievica writes `Снэйдэр`. Same for `аспектаў → асьпектаў`
(`аспэктаў`) and `спартсменам → спартсьменам` (`спартсмэнам`). The two halves of the
loanword adaptation are not independent, and applying half of it is worse than none.

**`other` was one question, not a miscellany — and it is now answered.** Thirty of its
thirty-five dev cases are у/ў: `Украіны`/`Ўкраіны`, `Усходняй`/`Ўсходняй`, a capitalised
proper noun after a word ending in a vowel. This went unimplemented for one reason — the
2005 book is not redistributable, `data/reference/` is git-ignored, and a rule that
cannot be checked against the text does not get written here. `python
scripts/fetch_reference.py` restores it from the Wayback capture and verifies the
SHA-256, and the text settles it in one line:

> **§18.** Пасьля галосных літараў на месцы у пішацца ў, калі на яго не прыпадае націск:
> … ва Ўфе, сталіца Ўкраіны, Марыя Ўласевіч …

`сталіца Ўкраіны` is the corpus case verbatim. The class went from **0/35 to 15/35**.
The earlier note in this repo guessed §15 — §15 is і → ы after a prefix — which is why
it was marked UNVERIFIED and left unwritten rather than shipped on a guess.

**Read this next to the precision figures, not instead of them.** Those are not wrong:
the converter changes very little it should not. It simply changes less than a
Taraškievica writer would, and until this harness existed there was no way to say so.

### Unresolved: measured, not guessed

The API can flag a passthrough word as a possible miss — the `unresolved` field in
`docs/API.md` — using the same shape-based triggers built for the (off-by-default)
disambiguation classifier's candidate net (`Converter.is_ambiguous`; e.g. a consonant
before е, the shape of a loan vs. native е/э split). Whether that heuristic is worth
showing a caller is itself measurable, using this section's own ground truth: a
flagged word is a real miss when the dev parallel corpus attests it should have
changed, the same signal `measure_recall` scores misses against.

| direction | flag precision | flag rate |
|---|---|---|
| N → T | 15.2% | 15.3% |
| T → N | 1.9% | 12.9% |

*Flag precision* — of flagged words, the share that were real misses. *Flag rate* —
flagged words as a share of every dev token, not just the passthrough ones. The bar for
shipping this on by default was precision ≥ 0.5 and rate ≤ 2%, in both directions; it
misses both, by a wide margin, in both directions, so `unresolved` ships **off**:
`Converter.convert()` takes `unresolved: bool = False`, and `/v1/convert` returns `[]`
until a `?unresolved=true` request flag reaches it. `[дтнмсзпбвфр]е` — consonant, then
е, anywhere in the word — is the biggest offender: it fires on ordinary native
vocabulary far more often than on an actual loanword, which is exactly the shape a
bigger stem inventory resolves outright (`### What the next review session is worth`,
next) rather than leaving ambiguous. Both figures are ratcheted in
`data/eval/baseline.json` next to recall and precision, so a heuristic tweak that
quietly makes either worse fails the build instead of shipping unnoticed.

### What the next review session is worth

`scripts/mine_wikidata_labels.py` mines candidate stems from Wikidata labels, which carry
a `be` and a `be-tarask` string for the same item and are therefore aligned by
construction — no sentence alignment, no similarity threshold, no bias from either, and
CC0 rather than CC BY-SA. 1,584 candidates are queued in `data/review/stem_candidates.tsv`.

They are **not** ranked by impact alone. Impact counts the tokens a stem touches, and a
short stem matching native vocabulary has the largest blast radius by construction: `бел`,
mined from the name *Бела*, scores 454,828 on the Narkamaŭka frequency list and every one
of those tokens is *беларускі*, *беларусь*, *Беларусі*. Ranking that way put eight
catastrophic candidates above the first good one.

So each candidate is screened against 15M tokens of genuine be-tarask
(`data/corpora/frequency_tarask.tsv`, built with the recall corpus's own held-out articles
excluded, so a stem is never believed partly on the evidence of sentences it is later
scored against), and the queue is sorted by that verdict first:

| verdict | n | example evidence |
|---|---|---|
| `supported` | 165 | `амэрыканскі`=2407 vs `амерыканскі`=0 |
| `unknown` | 1376 | too rare in be-tarask to say |
| `refuted` | 43 | `беларусі`=54829 vs `бэларусі`=0 |

`scripts/recall_curve.py` then answers the question that actually decides whether to spend
the session, without writing anything to `data/`:

```
 stems added      in-scope recall [95% CI]               precision
           0              74.2% [72%, 76%]        95.3% [94%, 96%]
          25              77.8% [76%, 80%]        95.6% [94%, 97%]
          50              78.8% [77%, 81%]        95.8% [95%, 97%]
          75              79.7% [78%, 82%]        95.8% [95%, 97%]
         100              80.6% [79%, 82%]        95.7% [95%, 97%]
         125              81.3% [79%, 83%]        95.7% [95%, 97%]
         144              81.6% [80%, 83%]        95.7% [95%, 97%]
```

The first 25 rows are worth as much as the next four batches together, which is the
argument for reviewing one batch and stopping rather than promising six. The queue is
built to be worked 25 at a time for that reason, and overlapping rows are folded
automatically — `амерык` absorbs `амерыкан`, `амерыканск`, `амерыканскі`, `амерыканска`,
which were four rows and one fact — into the shortest stem that is both supported by the
be-tarask screen and safe against the negative set. 68 rows collapsed that way; the ones
folded in are named in the row's `covers` column, so a reviewer who distrusts a short
stem can accept the narrower ones instead.

Recall rising while precision holds is the result to want: the stems are changing
loanwords, not catching native vocabulary. **Accepting them is still a human step** — the
inventory is what keeps the false-positive rate at zero, and the queue still contains
things a person should catch, such as three overlapping rows for one fact (`амерык`,
`амерыкан`, `амерыканск`).

### The gates

Three of them, because a stem batch can go wrong in three different ways.

**The ratchet** (`data/eval/baseline.json`, `tests/test_ratchet.py`). Every measured
figure is recorded at its best observed value and the build fails when a later run falls
below it. `scripts/update_baseline.py` refuses to write a metric that dropped unless it
is given a reason, and the reason is stored next to the number — so making a figure worse
is a sentence somebody wrote, not a rerun. The corpus is fingerprinted, because a
baseline from a different set of sentences is not a floor but a different measurement,
and because otherwise the way to make a failing ratchet pass would be to grow the corpus
until the number came back.

**The negative set and the dev-precision floor** — two tests in
`tests/test_negative_set.py` that fail the build when a lexicon batch goes wrong.

`data/eval/negative.tsv` holds **3,213 word forms the converter must not change**: forms
both wikis wrote identically at an aligned position, at least twice, in the **train** split
only, and which the corpus never shows converted anywhere else — so one author's lapse
cannot be mistaken for agreement. Rebuilding is **additive**: a pinned row is never
dropped, because otherwise "add bad stem, rebuild, commit" would turn a caught regression
into a green build.

The second test holds dev precision above a floor. It is a floor and not 99%, because
almost every dev "false positive" is the converter correctly applying a cited rule
(`Салідарнасць → Салідарнасьць`, `не → ня`) to an article that had not been converted.
The exact gate is the negative set; this one catches the large drop a bad batch causes.

Both earned their keep immediately. `scripts/mine_wikidata_labels.py` used to write its
review queue into `data/lexicon/stems/`, which `read_stem_sources` globs, so 1,584
unreviewed candidates became live inventory and the converter began writing *Бэларусь*,
*пэршы* and *сэльсавет* without a single test going red. These two failed, and named the
cause.

## Coverage — what the converter can even see

```bash
# from a dump, not the API: one reproducible file, no rate limit, no sampling
python scripts/build_frequency_list.py --dump bewiki-latest-pages-articles.xml.bz2
pravapis eval --coverage --top 20000
```

`data/corpora/frequency_be.tsv` is the top 20,000 Narkamaŭka forms from 266,050
be.wikipedia articles — 44.1M tokens, 77.0% of them covered by those 20,000 forms.

| what the converter knows | forms | of types | of tokens |
|---|---|---|---|
| stem — loan | 492 | 2.5% | 1.8% |
| stem — native guard | 278 | 1.4% | 1.2% |
| lexicon entry | 137 | 0.7% | 1.3% |
| a rule changes it (no etymology needed) | 2,123 | 10.6% | 7.8% |
| nothing | 16,970 | 84.9% | 87.8% |

Recall is measured on sentences that happened to align. Coverage asks a blunter question
with no sampling in it: of the word forms Belarusian text is made of, how many does the
converter know anything about? Each of the top 20,000 forms is assigned to exactly one of
*stem* (loan or native guard), *lexicon entry*, *a rule changes it anyway*, or *nothing*,
and each is reported by type and by token — the share of the vocabulary and the share of
running text, which are very different numbers.

A low stem figure is not by itself a gap. Stems exist only to tell the loanword rules
that a word is a borrowing; native vocabulary needs none, and most forms are native. The
figure that matters is stem coverage read next to loanword recall above.

## Round-trip drift

```bash
pravapis eval --round-trip --round-trip-dump data/eval/roundtrip_failures.tsv
```

N → T → N on unlabelled Narkamaŭka text that is deliberately **not** the gold set, so
fixing what it finds does not tune the converter on its own test data. Reports the
word-level and sentence-level identity rates and dumps every word that did not come back,
grouped by the pair of stages that broke it (`palat.assim | palat.unassim`), which is
usually enough to see the cause without opening the rule files.

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
| **Change accuracy** (249 words that should change) | **98.4%** | 0.0% |
| False-positive rate (2,182 words that should not) | **0.0%** | 0.0% |
| Word accuracy (2,431 words) | 99.8% | 89.8% |
| Sentence accuracy | 96.7% | 23.3% |

**This figure was 94.7% on a corrupted set, and the correction is worth reading.** The
Taraškievica column is supposed to be the untouched original — the whole independent
measurement rests on that. 28 of the 150 rows had drifted from `corpus.tsv`, by 50
character edits, every one of them in this converter's direction: 11 × `і → й` (the
*optional* §13 rule), 10 × `і → ы`, inserted and deleted `ь`, one `ґ → г` — which is this
project's own ґ policy — and 7 vocabulary swaps (`работа → праца`, `саюз → звяз`,
`германскі → нямецкі`, `пастаноўка → інсцэнізацыя`). Somebody had run the gold's *input*
through the converter. All 28 were restored from the corpus; the hand-written Narkamaŭka
column was not touched.

The number rose because the repair deleted 26 change-opportunities that should never have
existed (264 → 238), including the vocabulary swaps a spelling converter cannot and should
not perform — **not** because the converter improved. That is the same
scored-against-itself trap `gold.tsv` exists to document, arriving by a new route, so
`test_independent_gold_taraskievica_column_is_the_untouched_corpus` now asserts every
Taraškievica column appears verbatim in `corpus.tsv`.

The false-positive rate is 0.0% on both gold sets. It got there by a route worth
recording: the audit and the gold used to contradict each other on four changes
(`сымбалізм → сімвалізм`, `максымум → максімум`, `спэктаклі → спектаклі`,
`сымбалізуе → сімвалізуе`), and those were left standing rather than reconciled in the
converter's favour until the project owner ruled on them — Narkamaŭka writes `сімвалізм`
(Slavic *в* against Taraškievica's Greek *б*), `максімум` (soft *s* before *i*) and
`спектаклі`. Eleven gold rows had a Taraškievica spelling in their Narkamaŭka column and
were corrected.

`scripts/check_gold_t2n.py` is what makes that mechanical rather than a matter of reading:
it runs the Narkamaŭka column back through the converter and reports any row that changes,
since a finished row cannot. Both gold files now report zero.

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

## Install

```bash
uv sync                  # core: rules + lexicon
uv sync --extra ml       # + experimental classifier, opt-in only (pip install pravapis[ml])
```

## The data is a specification

Every data file is described by a JSON Schema in [`data/schemas/`](data/schemas/), and
those schemas are **normative**. An implementation in another language reads them; it
does not read `src/pravapis/rules/engine.py` and infer the format from whatever the
parser happens to tolerate.

| Schema | Describes |
|---|---|
| `rules.schema.json` | `data/rules/*.yaml` — both accepted layouts, the pattern/function alternative, the etymology gate |
| `stems.schema.json` | `data/lexicon/stems/*.tsv` — the file dialect in `x-tsv`, the parsed row in `$defs/row` |
| `translit.schema.json` | `data/translit/*.yaml` — the closed condition vocabulary, coverage |
| `conformance.schema.json` | one line of `conformance/cases.jsonl` |

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

[`data/VERSION`](data/VERSION) carries its own semver, and
[`data/VERSIONING.md`](data/VERSIONING.md) says what a bump means — a stem added is a
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

[`conformance/cases.jsonl`](conformance/) flattens every inline rule test, every inline
transliteration test, the trusted gold subset and the independent held-out sentences into
one file of self-contained cases. **A port is correct iff it passes it.** 914 cases today;
`manifest.json` records the data version and a sha256, because a port claims conformance
*for a data version*, never in the abstract.

Each case says at which level it applies — `rule` cases exercise one rule in isolation,
`gold` and `heldout` cases go through the public API — since running a unit case through
the whole pipeline would fail for the wrong reason (`palat.assim` turns `свіння` into
`сьвіння`; the pipeline goes on to write `сьвіньня`).

Two decisions worth stating:

- **Only one direction is exported per gold file.** `gold.tsv` declares
  `# origin: narkamauka`, so contracting T → N from it would freeze a self-consistency
  figure as though it were accuracy. The T → N cases come from the genuine Taraškievica
  set instead.
- **The 11 cases the reference implementation does not pass go to
  `known_failures.jsonl`**, not into the contract. Putting them in `cases.jsonl` would
  make it unpassable; dropping them would hide known gaps behind a green check.

## Library

The public signature is frozen, and it is the same in every implementation:

```python
from pravapis import convert

convert("снег", {"from": "narkamauka", "to": "taraskievica"})
# ConversionResult(text='сьнег', ...)
#   .to_dict() == {
#     "text": "сьнег",
#     "changes": [{"from": "снег", "to": "сьнег", "offset": 0,
#                  "rule": "palat.assim", "class": "rule",
#                  "citation": "Збор 2005, §29"}],
#   }
```

`changes` is **always** returned, never behind a flag: the cascade has to decide what
happened to every word in order to convert it at all, so reporting those decisions costs
an attribute read — and making it opt-in only guarantees that the explanation and the
conversion drift apart. `explain()` is now a view over this result rather than a second
pass over the text; all it adds is the per-rule trace.

`offset` indexes the **sanitized** input (`sanitize` is idempotent and public, so a
caller can reproduce the string these index into). `class` is the cascade stage that
resolved the word; `citation` is where the evidence comes from, and is `null` for a
lexicon hit, whose evidence is the entry itself.

```python
from pravapis import Converter, Orthography, Script, convert

convert("Не быў без мяне", Orthography.TARASKIEVICA)   # 'Ня быў безь мяне' (older form, returns str)

conv = Converter.from_config()          # loads data/ once; reuse it
result = conv.convert("сістэма", Orthography.TARASKIEVICA)
result.text, result.stats, result.changes

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
pravapis eval --recall --misses misses.tsv          # recall + precision, dev split
pravapis eval --recall --split test                 # the frozen split; milestones only
pravapis eval --recall -d narkamauka                # T → N recall, not just N → T
pravapis eval --coverage --top 20000                # stem/lexicon coverage by frequency
pravapis eval --round-trip                          # N→T→N identity rate + dump
pravapis audit data/eval/tarask/corpus.tsv --to narkamauka --out audit.tsv
pravapis audit data/eval/tarask/corpus.tsv --rule palat.unassim --sample 15
pravapis validate-data                              # data vs data/schemas/
pravapis export-conformance                         # regenerate the contract corpus
pravapis export-conformance --check                 # fail if it is stale
pravapis bench --size 10mb

# growing the lexicon — mine, screen, decide, then review
python scripts/mine_wikidata_labels.py --pages 60000   # → data/review/stem_candidates.tsv
python scripts/recall_curve.py --steps 0,25,50,100,165 # what accepting them would buy
python scripts/build_negative_set.py                   # refresh the precision gate
python scripts/update_baseline.py                      # ratchet the new figures up
python scripts/update_baseline.py --milestone          # ... and read the frozen split

# the codification itself (git-ignored, copyrighted; fetched and hash-checked)
python scripts/fetch_reference.py
pravapis serve
```

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/convert` | `{"text", "direction", "explain"}` → converted text, stats, and `changes` (always) |
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
the same way, that a future `GET /v1/version` reports as `data_hash` — the artifact
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
data/schemas/    JSON Schemas — the normative spec for every data format
data/VERSION     the data package's own semver (see data/VERSIONING.md)
conformance/     cases.jsonl, known_failures.jsonl, manifest.json — the cross-language
                 contract, generated by `pravapis export-conformance`
data/rules/      YAML rules (palatalization, loanwords, morphology), each rule cited
data/translit/   Łacinka + official-2007 scheme tables, with inline tests
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
api/             Vercel function (convert.py)
public/          the conversion form served at /
data/stress/     GrammarDB first-syllable stress tables (CC BY-SA 4.0)
tests/           pytest + hypothesis
benchmarks/      pytest-benchmark
```

## License

MIT
