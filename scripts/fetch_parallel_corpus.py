"""Align be ↔ be-tarask articles by title and mine sentence pairs from them.

    python scripts/fetch_parallel_corpus.py --articles 400

Every evaluation set pravapis has so far says what the converter gets *right* on text
somebody chose. None of them can say what it **misses**, because a miss is a change that
should have happened and there is no list of those. This builds one: the same article,
written independently in Narkamaŭka on be.wikipedia.org and in Taraškievica on
be-tarask.wikipedia.org, aligned sentence by sentence and diffed token by token. Each
differing token pair is a change the converter ought to produce.

**These are not translations of each other.** The two wikis are independently written,
so most sentences do not correspond at all, and the aligner is deliberately strict:
same token count, a high share of tokens identical in both, and a clear margin over the
runner-up. What survives is a biased sample — short, formulaic, date- and
definition-shaped sentences align far more often than prose — and the recall computed
from it inherits that bias. It is still the only direct evidence of misses available,
and a biased measurement that says so beats no measurement.

Output:

    data/corpora/parallel.tsv       narkamaŭka <TAB> taraškievica <TAB> provenance…
    data/corpora/parallel.README.md CC BY-SA 4.0 attribution

Re-running keeps pairs already fetched and appends only new ones.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import regex

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.normalize import sanitize  # noqa: E402
from pravapis.scope import neutral_fold  # noqa: E402

TARASK_API: Final[str] = "https://be-tarask.wikipedia.org/w/api.php"
NARK_API: Final[str] = "https://be.wikipedia.org/w/api.php"
WIKIDATA_API: Final[str] = "https://www.wikidata.org/w/api.php"
USER_AGENT: Final[str] = "pravapis-eval/0.1 (https://github.com/sewstie/pravapis; research)"
OUT_DIR: Final[Path] = ROOT / "data" / "corpora"
OUT_TSV: Final[Path] = OUT_DIR / "parallel.tsv"

_SENTENCE_SPLIT: Final[regex.Pattern[str]] = regex.compile(r"(?<=[.!?…])\s+(?=\p{Lu})")
_CYRILLIC_ONLY: Final[regex.Pattern[str]] = regex.compile(r"^[\p{Cyrillic}\s\p{P}\d«»—–-]+$")
_WORD: Final[regex.Pattern[str]] = regex.compile(r"[\p{Cyrillic}’ʼ'-]+")

#: An aligned pair must be this similar on identical tokens, and the runner-up must be
#: this much worse. Both are deliberately strict: a wrong alignment does not produce a
#: weaker signal, it produces a *false* ground-truth change, which is worse than none.
#: Similarity is measured on *folded* tokens, so it now reflects content overlap alone
#: and can be demanded at a higher level than a raw-string threshold could: raising this
#: no longer discriminates against sentences dense in orthographic change.
MIN_SIMILARITY: Final[float] = 0.75
MIN_MARGIN: Final[float] = 0.15
MIN_WORDS: Final[int] = 4
MAX_WORDS: Final[int] = 40

#: Article-level split. The same loanword recurs throughout an article — a biography of
#: Chopin says Шапэн thirty times — so splitting by sentence would put the same stem on
#: both sides of the line and let a stem mined from train score itself on test. The unit
#: has to be the article. Shares are of articles, not sentences, so the sentence counts
#: come out uneven; that is correct and not worth "fixing".
SPLITS: Final[tuple[tuple[str, float], ...]] = (("train", 0.6), ("dev", 0.2), ("test", 0.2))


@dataclass(frozen=True, slots=True)
class Pair:
    narkamauka: str
    taraskievica: str
    title_be: str
    revid_be: int
    title_tarask: str
    revid_tarask: int
    similarity: float
    split: str


def split_of(title: str) -> str:
    """Which split an article belongs to, from a stable hash of its title.

    Python's ``hash`` is salted per process, so it is useless for anything that has to
    stay the same tomorrow. blake2b over the title gives the same answer on every
    machine and every run, which is what makes the split reproducible — and the value is
    written into the corpus file anyway, so the frozen split survives even a change to
    this function.
    """
    digest = hashlib.blake2b(title.encode("utf-8"), digest_size=8).digest()
    position = int.from_bytes(digest, "big") / float(1 << 64)
    cumulative = 0.0
    for name, share in SPLITS:
        cumulative += share
        if position < cumulative:
            return name
    return SPLITS[-1][0]


def _get(api: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"{api}?{urllib.parse.urlencode({**params, 'format': 'json'})}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def random_titles(count: int) -> dict[str, str]:
    """``be-tarask title -> Wikidata item id`` for random main-namespace articles."""
    out: dict[str, str] = {}
    attempts = 0
    while len(out) < count and attempts < count:
        attempts += 1
        data = _get(
            TARASK_API,
            {
                "action": "query",
                "generator": "random",
                "grnnamespace": "0",
                "grnlimit": "30",
                "prop": "pageprops",
                "ppprop": "wikibase_item",
            },
        )
        for page in data.get("query", {}).get("pages", {}).values():
            qid = (page.get("pageprops") or {}).get("wikibase_item")
            if qid:
                out.setdefault(page["title"], qid)
        time.sleep(0.2)  # be a good API citizen
    return dict(list(out.items())[:count])


def be_titles_for(qids: list[str]) -> dict[str, str]:
    """``Wikidata item id -> be.wikipedia title``.

    Interlanguage links have lived in Wikidata since 2013, not in the wikitext, so
    ``prop=langlinks`` on be-tarask returns almost nothing. The sitelink is the real
    statement that two articles are about the same thing, which is exactly the claim
    the alignment rests on.
    """
    found: dict[str, str] = {}
    for i in range(0, len(qids), 50):
        data = _get(
            WIKIDATA_API,
            {
                "action": "wbgetentities",
                "ids": "|".join(qids[i : i + 50]),
                "props": "sitelinks",
                "sitefilter": "bewiki",
            },
        )
        for qid, entity in (data.get("entities") or {}).items():
            sitelink = (entity.get("sitelinks") or {}).get("bewiki")
            if sitelink:
                found[qid] = sitelink["title"]
        time.sleep(0.2)
    return found


def article_text(api: str, title: str) -> tuple[int, str] | None:
    """``(revid, plain text)`` for one article.

    One request per article: the API refuses to return whole-article extracts in
    batches ("exlimit was too large for a whole article extracts request, lowered to
    1"), and intro-only extracts would narrow an already narrow sample to definition
    sentences.
    """
    data = _get(
        api,
        {
            "action": "query",
            "titles": title,
            "prop": "extracts|revisions",
            "explaintext": "1",
            "rvprop": "ids",
            "redirects": "1",
        },
    )
    for page in data.get("query", {}).get("pages", {}).values():
        text = page.get("extract") or ""
        revs = page.get("revisions") or [{}]
        if text and revs[0].get("revid"):
            return int(revs[0]["revid"]), text
    return None


def sentences_of(text: str) -> list[str]:
    out: list[str] = []
    for raw in _SENTENCE_SPLIT.split(text.replace("\n", " ")):
        s = sanitize(" ".join(raw.split()))
        if not s or not _CYRILLIC_ONLY.match(s):
            continue
        if not MIN_WORDS <= len(_WORD.findall(s)) <= MAX_WORDS:
            continue
        out.append(s)
    return out


def words(sentence: str) -> list[str]:
    """Word tokens, **folded**, so orthography costs nothing when sentences are compared.

    This is the whole anti-bias measure. Scored on raw strings, a sentence pair is less
    similar the more orthographic changes it contains — so a similarity threshold drops
    precisely the sentences with the most work in them, and the corpus ends up
    under-representing the thing it exists to measure. Folding both sides first removes
    that gradient: a sentence with fifteen softness marks scores exactly like one with
    none.

    The fold is fixed and etymology-free (see pravapis.scope). It is deliberately not
    "convert one side and compare", which would keep the sentences the converter already
    handles and drop the ones it does not — the same bias, pointing the other way, and
    much harder to spot.
    """
    return [neutral_fold(w) for w in _WORD.findall(sentence)]


def similarity(a: list[str], b: list[str]) -> float:
    """Share of positions holding the same folded word. Zero unless the lengths match.

    Requiring the same token count is the cheapest strong signal that two sentences are
    the same sentence: no orthographic difference pravapis models adds or removes a
    word, so a length mismatch means the sentences genuinely differ.
    """
    if not a or len(a) != len(b):
        return 0.0
    return sum(x == y for x, y in zip(a, b, strict=True)) / len(a)


def align(nark_sentences: list[str], tarask_sentences: list[str]) -> list[tuple[str, str, float]]:
    """Greedy one-to-one alignment, keeping only unambiguous matches."""
    nark_words = [words(s) for s in nark_sentences]
    pairs: list[tuple[str, str, float]] = []
    used: set[int] = set()
    for tarask in tarask_sentences:
        tw = words(tarask)
        scored = sorted(
            ((similarity(nw, tw), i) for i, nw in enumerate(nark_words) if i not in used),
            reverse=True,
        )
        if not scored:
            break
        best, index = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        if best < MIN_SIMILARITY or best - runner_up < MIN_MARGIN:
            continue
        if nark_sentences[index] == tarask:
            # Byte-identical sentences carry no change and would only pad the
            # denominator. Note this is *not* the same as a folded similarity of 1.0,
            # which is the best possible evidence: a pair that differs only
            # orthographically is exactly what this corpus is for.
            continue
        used.add(index)
        pairs.append((nark_sentences[index], tarask, best))
    return pairs


def read_existing(path: Path) -> set[tuple[str, str]]:
    if not path.is_file():
        return set()
    rows: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.add((parts[0], parts[1]))
    return rows


HEADER = (
    "# narkamauka<TAB>taraskievica<TAB>title_be<TAB>revid_be<TAB>title_tarask"
    "<TAB>revid_tarask<TAB>similarity<TAB>split\n"
    "#\n"
    "# Sentence pairs mined from be.wikipedia.org and be-tarask.wikipedia.org by\n"
    "# scripts/fetch_parallel_corpus.py. The two wikis are written independently, so\n"
    "# these are not translations: they are sentences the aligner judged to be the same\n"
    "# sentence. The sample is biased towards short, formulaic sentences.\n"
    "#\n"
    "# similarity is measured on NEUTRALLY FOLDED tokens (pravapis.scope.neutral_fold),\n"
    "# so orthographic density does not affect whether a pair is kept. Scoring raw\n"
    "# strings would drop exactly the sentences carrying the most change.\n"
    "#\n"
    "# split is assigned PER ARTICLE, never per sentence: the same loanword recurs all\n"
    "# through an article, so a sentence-level split would leak it across the line. The\n"
    "# value is written here rather than recomputed, which is what freezes it.\n"
    "#\n"
    "# MEASUREMENT ONLY. Never read by lexicon building, stem mining or model training:\n"
    "# it exists to measure recall, and a set you have fitted to measures nothing.\n"
    "# Stem mining reads the TRAIN split only; test is touched at milestones.\n"
    "# Text is CC BY-SA 4.0; see parallel.README.md.\n"
)

ATTRIBUTION = """# data/corpora/parallel.tsv — aligned be ↔ be-tarask sentence pairs

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
"""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--articles", type=int, default=300, help="be-tarask articles to sample")
    parser.add_argument("--out", type=Path, default=OUT_TSV)
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = read_existing(args.out)
    print(f"{len(existing)} pair(s) already in {args.out}")

    print(f"sampling {args.articles} random be-tarask articles…")
    titles = random_titles(args.articles)
    be_title = be_titles_for(sorted(set(titles.values())))
    matched = [(t, be_title[q]) for t, q in titles.items() if q in be_title]
    print(f"  {len(titles)} articles, {len(matched)} with a be counterpart in Wikidata")

    fresh: list[Pair] = []
    aligned_articles = 0
    for n, (title_tarask, title_be) in enumerate(matched, 1):
        if n % 25 == 0:
            print(f"  …{n}/{len(matched)} articles, {len(fresh)} pairs so far")
        tarask = article_text(TARASK_API, title_tarask)
        time.sleep(0.2)
        if tarask is None:
            continue
        be = article_text(NARK_API, title_be)
        time.sleep(0.2)
        if be is None:
            continue
        revid_tarask, text_tarask = tarask
        revid_be, text_be = be
        pairs = align(sentences_of(text_be), sentences_of(text_tarask))
        if pairs:
            aligned_articles += 1
        for nark, tarask_sentence, score in pairs:
            if (nark, tarask_sentence) in existing:
                continue
            existing.add((nark, tarask_sentence))
            fresh.append(
                Pair(
                    nark,
                    tarask_sentence,
                    title_be,
                    revid_be,
                    title_tarask,
                    revid_tarask,
                    score,
                    split_of(title_be),
                )
            )

    new_file = not args.out.is_file()
    with args.out.open("a", encoding="utf-8", newline="\n") as fh:
        if new_file:
            fh.write(HEADER)
        for p in fresh:
            fh.write(
                f"{p.narkamauka}\t{p.taraskievica}\t{p.title_be}\t{p.revid_be}\t"
                f"{p.title_tarask}\t{p.revid_tarask}\t{p.similarity:.3f}\t{p.split}\n"
            )
    readme = OUT_DIR / "parallel.README.md"
    if not readme.is_file():
        readme.write_text(ATTRIBUTION, encoding="utf-8")

    print(
        f"+{len(fresh)} new pair(s) from {aligned_articles}/{len(matched)} article pairs "
        f"→ {args.out} ({len(existing)} total)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
