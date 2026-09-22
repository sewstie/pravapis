# data/corpora/parallel.tsv — aligned be ↔ be-tarask sentence pairs

Mined by `scripts/fetch_parallel_corpus.py` from two independently written wikis:

- **be.wikipedia.org** — Narkamaŭka
- **be-tarask.wikipedia.org** — Taraškievica

Articles are matched by the `be` interlanguage link the be-tarask article declares;
sentences within a matched article pair are aligned by token overlap. Revision ids are
recorded for every row so the sample is reproducible and attributable.

## What it is for

It is the only direct evidence of **misses** available: a change the converter should
have made and did not. Every other evaluation set in this repository can say what the
converter gets right on text that somebody selected; none can enumerate what it fails to
do, because that requires knowing the right answer for text nobody wrote for the purpose.

## What it is not

The two wikis are not translations of each other. Most sentences do not correspond, and
the aligner rejects everything it is not confident about, so the surviving sample skews
short and formulaic. Recall measured on it is recall *on sentences that align*, which is
stated wherever the number is reported.

Neither is it reviewed. A differing token pair is evidence of a difference, not proof
that the difference is orthographic — the two wikis also make different word choices.
`pravapis eval --recall` buckets that case separately and reports a bound rather than a
single number.

## Licence

Text from both wikis is CC BY-SA 4.0. Attribution is the article title plus the
revision id, both recorded per row.
