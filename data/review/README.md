# data/review — proposals waiting on a person

Nothing in this directory is read by the converter. It is the queue: machine-generated
proposals that need a judgement before they can become data.

## Why it is not under `data/lexicon/stems/`

Because it was, and that was a bug. `pravapis.lexicon.stems.read_stem_sources` globs
`data/lexicon/stems/*.tsv`, and a candidates row happens to share its first six columns
with a stems row. So writing the queue there loaded 1,584 unreviewed stems into the live
inventory — including `бел` → `бэл`, mined from the name *Бела* — and the converter began
writing *Бэларусь*, *пэршы* and *сэльсавет* without a single test going red.

Three things changed after that:

- the queue lives here, outside anything that is loaded;
- the directory loader now requires the `#!schema` declaration, so an undeclared file in
  the inventory directory is ignored rather than trusted (`tests/test_stems.py`);
- `data/eval/negative.tsv` and the dev-precision gate exist, which is what *caught* it —
  both failed loudly and named the cause ("a new stem is probably catching native
  vocabulary").

## `stem_candidates.tsv`

Written by `scripts/mine_wikidata_labels.py` from Wikidata labels, which carry a `be`
and a `be-tarask` string for the same item and are therefore aligned by construction.

Read it top-down. It is sorted by **verdict** first and impact second, and the verdict
comes from 17M tokens of genuine be-tarask (`data/corpora/frequency_tarask.tsv`):

| verdict | meaning |
|---|---|
| `supported` | Taraškievica writes the converted form and not the original. Work worth doing. |
| `unknown` | too rare in be-tarask to say. Read the blast radius yourself. |
| `refuted` | Taraškievica writes the **original** — the stem would corrupt real words. |

Sorting by impact alone put the most destructive candidates first, because a short stem
matching native vocabulary has the largest blast radius by construction. `бел` scores
454,828 on the Narkamaŭka frequency list and every one of those tokens is *беларускі*,
*беларусь*, *Беларусі*.

The `evidence` column carries the counts behind the verdict, so it can be checked rather
than believed, and `blast_radius` carries the frequent forms the stem would also match —
a `!` marks the ones the converter leaves alone today, which are what would start moving.

## The batch loop

Review is the bottleneck, so the queue is built to be worked **25 rows at a time**, and
each session ends with a number rather than a feeling. The rows are already in the order
worth reading — verdict first, impact second — so batch N is just the next 25 lines.

```bash
python scripts/recall_curve.py --steps 0,25,50,75,100,125,144   # what each batch is worth
#   ... review and accept rows 1-25 into data/lexicon/stems/stems.tsv ...
python -m pytest tests/test_negative_set.py tests/test_ratchet.py  # did it break anything?
python scripts/update_baseline.py                                  # record the gain
```

Measured on dev, on the corpus as committed:

| batch | rows | dev recall | gain | precision |
|---|---|---|---|---|
| — | 0 | 74.2% [72, 76] | — | 95.3% |
| 1 | 25 | 77.8% [76, 80] | **+3.6** | 95.6% |
| 2 | 50 | 78.8% [77, 81] | +1.0 | 95.8% |
| 3 | 75 | 79.7% [78, 82] | +0.9 | 95.8% |
| 4 | 100 | 80.6% [79, 82] | +0.9 | 95.7% |
| 5 | 125 | 81.3% [79, 83] | +0.7 | 95.7% |
| 6 | 144 | 81.6% [80, 83] | +0.3 | 95.7% |

The first batch is worth as much as the next four together, which is the argument for
doing one and stopping rather than promising six. Precision does not move across the
whole range — that is the result to want, and the reason to read the precision column
every time: recall rising while precision falls is a stem that found native vocabulary,
not a stem doing its job.

`scripts/update_baseline.py` then writes the new figure into `data/eval/baseline.json`,
and `tests/test_ratchet.py` holds it from that commit onward. A later batch that undoes
this one fails the build instead of quietly cancelling it out.

**Accepting a candidate** means copying the first six columns into
`data/lexicon/stems/stems.tsv`, giving it a real `source` and `provenance`, and adding a
`native` guard for any false friend in its blast radius. Longest match then does the
rest: native `класц` beats loan `клас` on *класці*. Bump `data/VERSION` by a minor.
