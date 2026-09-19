# data/eval/tarask — genuine Taraškievica, for independent T → N evaluation

`corpus.tsv` holds sentences sampled from **be-tarask.wikipedia.org** by
`scripts/fetch_tarask_corpus.py`, one per line, with the article title and the exact
revision id they were taken from.

## Why this exists

`data/eval/gold.tsv` is Narkamaŭka in origin: its Taraškievica side was written by
applying the 2005 norm to Narkamaŭka text from the Paznaj site. Scoring T → N on it
therefore measures whether the converter can undo a transformation derived from the same
reading of the norm it implements — self-consistency, not accuracy. This corpus is text
no one derived from Narkamaŭka, so it can say something the gold set cannot.

## Licence and attribution

Text from **be-tarask.wikipedia.org**, © its contributors, licensed under
**Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
https://creativecommons.org/licenses/by-sa/4.0/. Each row names the article and the
revision id it came from, which is the attribution.

Changes: text split into sentences, whitespace normalised, Unicode sanitised
(`pravapis.normalize.sanitize`), and filtered to sentences carrying a Taraškievica
marker. `gold_t2n.tsv` additionally carries a Narkamaŭka rendering of each sentence,
which is a derivative work.

**This corpus and `gold_t2n.tsv` are distributed under CC BY-SA 4.0**, like
`data/stress/`. The pravapis source code remains MIT.

## Caveat worth knowing

be-tarask is community-written and does not follow the 2005 codification uniformly —
some articles use older Taraškievič conventions. A disagreement between the converter
and this corpus is therefore not automatically the converter's fault. Where it matters,
check the construction against the Збор правілаў 2005 prose in `data/reference/`, which
is expert-written Taraškievica by the codifier himself.
