"""Sample genuine Taraškievica sentences from be-tarask.wikipedia.org.

    python scripts/fetch_tarask_corpus.py --sentences 400

Every Taraškievica sentence pravapis has evaluated against so far was *derived*:
`data/eval/gold.tsv` starts from Narkamaŭka text off the Paznaj site and applies the
2005 norm to it, so scoring T → N on it largely asks whether the converter can undo a
transformation produced by the same reading of the norm it implements. That is
self-consistency, not accuracy.

This script fetches text nobody derived from Narkamaŭka: articles written by
Taraškievica writers. It is also the Taraškievica people actually type, which is what
will arrive at the API.

Only sentences carrying a **Taraškievica marker** are kept — an assimilative ь, a loan
э/ы, or ґ. A sentence with nothing to convert would pad the denominator with words that
cannot change in either direction and flatter every number computed from it.

Output:

    data/eval/tarask/corpus.tsv   sentence <TAB> article <TAB> revid
    data/eval/tarask/README.md    CC BY-SA 4.0 attribution (written once)

Revision ids make the sample reproducible and are what the licence attribution points
at. Re-running keeps sentences already fetched and appends only new ones, so the corpus
grows without invalidating review work already done against it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Final

import regex

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.normalize import sanitize  # noqa: E402

API: Final[str] = "https://be-tarask.wikipedia.org/w/api.php"
USER_AGENT: Final[str] = "pravapis-eval/0.1 (https://github.com/sewstie/pravapis; research)"
OUT_DIR: Final[Path] = ROOT / "data" / "eval" / "tarask"

#: Spellings that only Taraškievica produces. A sentence with none of them has nothing
#: to test: it would read identically in both orthographies.
MARKERS: Final[tuple[regex.Pattern[str], ...]] = tuple(
    regex.compile(p)
    for p in (
        r"[зсцнл]ь[бвгдзклмнпрстфхцчш]",  # assimilative softness: сьнег, зьмена
        r"[зсцн]ь[еёіюя]",  # сьвята, зьява
        r"дзь",  # судзьдзя
        r"ґ",  # plosive g
        r"\bэў",  # Эўропа
        r"[бвгдзкмпстфхр]л[яёю]",  # soft l in loans: плян, клюб
        r"[дтзсц]ы[кс]т",  # сыстэма-style ы
    )
)

_SENTENCE_SPLIT: Final[regex.Pattern[str]] = regex.compile(r"(?<=[.!?…])\s+(?=\p{Lu})")
_CYRILLIC_ONLY: Final[regex.Pattern[str]] = regex.compile(r"^[\p{Cyrillic}\s\p{P}\d«»—–-]+$")
_HAS_LETTERS: Final[regex.Pattern[str]] = regex.compile(r"\p{Cyrillic}{2,}")


def _get(params: dict[str, str]) -> dict[str, Any]:
    url = f"{API}?{urllib.parse.urlencode({**params, 'format': 'json'})}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def random_articles(count: int) -> list[tuple[str, int, str]]:
    """(title, revid, plain text) for ``count`` random main-namespace articles."""
    out: list[tuple[str, int, str]] = []
    while len(out) < count:
        batch = min(20, count - len(out))
        data = _get(
            {
                "action": "query",
                "generator": "random",
                "grnnamespace": "0",
                "grnlimit": str(batch),
                "prop": "extracts|revisions",
                "explaintext": "1",
                "rvprop": "ids",
            }
        )
        for page in data.get("query", {}).get("pages", {}).values():
            text = page.get("extract") or ""
            revs = page.get("revisions") or [{}]
            revid = int(revs[0].get("revid", 0))
            if text and revid:
                out.append((page["title"], revid, text))
        time.sleep(0.3)  # be a good API citizen
    return out


def has_marker(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(m.search(lowered) for m in MARKERS)


def sentences_of(text: str, *, min_words: int, max_words: int) -> list[str]:
    out: list[str] = []
    for raw in _SENTENCE_SPLIT.split(text.replace("\n", " ")):
        s = sanitize(" ".join(raw.split()))
        if not s or not _CYRILLIC_ONLY.match(s) or not _HAS_LETTERS.search(s):
            continue
        if not min_words <= len(s.split()) <= max_words:
            continue
        if not has_marker(s):
            continue
        out.append(s)
    return out


def read_existing(path: Path) -> dict[str, tuple[str, str]]:
    """sentence -> (article, revid), for rows already fetched."""
    if not path.is_file():
        return {}
    rows: dict[str, tuple[str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            rows[parts[0]] = (parts[1], parts[2])
    return rows


ATTRIBUTION = """# data/eval/tarask — genuine Taraškievica, for independent T → N evaluation

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
"""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sentences", type=int, default=400, help="how many to collect")
    ap.add_argument("--min-words", type=int, default=5)
    ap.add_argument("--max-words", type=int, default=40)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    args.out.mkdir(parents=True, exist_ok=True)
    corpus = args.out / "corpus.tsv"
    existing = read_existing(corpus)
    print(f"{len(existing)} sentences already present", file=sys.stderr)

    collected: dict[str, tuple[str, str]] = {}
    seen_articles = 0
    while len(collected) < args.sentences:
        for title, revid, text in random_articles(10):
            seen_articles += 1
            for s in sentences_of(text, min_words=args.min_words, max_words=args.max_words):
                if s not in existing and s not in collected:
                    collected[s] = (title, str(revid))
            if len(collected) >= args.sentences:
                break
        print(
            f"  {seen_articles} articles -> {len(collected)} new sentences",
            file=sys.stderr,
        )

    header = (
        "# sentence<TAB>article<TAB>revid\n"
        "# Genuine Taraškievica from be-tarask.wikipedia.org, CC BY-SA 4.0 — see README.md.\n"
        "# HELD OUT. Never read by lexicon building, stem mining, or model training.\n"
    )
    lines = [f"{s}\t{a}\t{r}" for s, (a, r) in {**existing, **collected}.items()]
    corpus.write_text(header + "\n".join(sorted(lines)) + "\n", encoding="utf-8")

    readme = args.out / "README.md"
    if not readme.is_file():
        readme.write_text(ATTRIBUTION, encoding="utf-8")

    print(f"wrote {corpus}: {len(lines)} sentences from {seen_articles} articles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
