# Accuracy

The full measurement behind the one-line accuracy claim in the README: what was
measured, on what text, against what baseline, and what is still missing. Numbers here
are pulled from `data/eval/baseline.json` and the commands shown; if this file and that
one ever disagree, the JSON is right and this file is stale.

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
restored — see [Independent T → N](#independent-t--n).

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

- **The gold Taraškievica is not native-reviewed.** It was written from Klasyčny
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

The API can flag a passthrough word as a possible miss — the `unresolved` field, see
[docs/API.md](API.md) for the wire-level decision — using the same shape-based triggers
built for the (off-by-default) disambiguation classifier's candidate net
(`Converter.is_ambiguous`; e.g. a consonant before е, the shape of a loan vs. native е/э
split). Whether that heuristic is worth showing a caller is itself measurable, using this
section's own ground truth: a flagged word is a real miss when the dev parallel corpus
attests it should have changed, the same signal `measure_recall` scores misses against.

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
bigger stem inventory resolves outright ("What the next review session is worth",
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

**Reviewed in full: 439 distinct changes, all judged `ok` — precision 100%.** `data/eval/tarask/REVIEW.md` has
the method; `pravapis audit --rule ... --sample N` and `--mark` are what made it an evening
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
