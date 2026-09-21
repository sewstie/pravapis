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

**Accepting a candidate** means copying the first six columns into
`data/lexicon/stems/stems.tsv`, giving it a real `source` and `provenance`, and adding a
`native` guard for any false friend in its blast radius. Longest match then does the
rest: native `класц` beats loan `клас` on *класці*. Bump `data/VERSION` by a minor.
