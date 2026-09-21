"""Build a Narkamaŭka word-form frequency list from be.wikipedia.org.

    python scripts/build_frequency_list.py --articles 4000 --top 20000

Coverage has to be measured against the forms Belarusian text is actually made of, not
against the forms the project happened to think of. There is no redistributable
frequency list for Belarusian that is easy to depend on, so this builds one from the
encyclopedia — reproducible from a revision-stamped sample, and in the same register as
the text the API receives.

Intro extracts are used rather than whole articles because they are the only extracts
the API will return in batches (20 per request against 1), which is the difference
between a minute and an hour. The cost is register: intros are definition-shaped, so
copulas and dates are over-represented relative to running prose. The header records
this, since a frequency list whose provenance is unstated will eventually be quoted as
though it were a balanced corpus.

Output: data/corpora/frequency_be.tsv — ``form<TAB>count``, most frequent first.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Final

import regex

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.normalize import sanitize  # noqa: E402

API: Final[str] = "https://be.wikipedia.org/w/api.php"
USER_AGENT: Final[str] = "pravapis-eval/0.1 (https://github.com/sewstie/pravapis; research)"
OUT: Final[Path] = ROOT / "data" / "corpora" / "frequency_be.tsv"

_WORD: Final[regex.Pattern[str]] = regex.compile(r"[\p{Cyrillic}’ʼ'-]+")


def _get(params: dict[str, str]) -> dict[str, Any]:
    url = f"{API}?{urllib.parse.urlencode({**params, 'format': 'json'})}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def sample_intros(articles: int) -> tuple[int, Counter[str]]:
    """Word-form counts over ``articles`` random be.wikipedia intros."""
    counts: Counter[str] = Counter()
    seen: set[str] = set()
    while len(seen) < articles:
        data = _get(
            {
                "action": "query",
                "generator": "random",
                "grnnamespace": "0",
                "grnlimit": "20",
                "prop": "extracts",
                "explaintext": "1",
                "exintro": "1",
                "exlimit": "max",
            }
        )
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            break
        for page in pages.values():
            title, text = page.get("title", ""), page.get("extract") or ""
            if not text or title in seen:
                continue
            seen.add(title)
            for word in _WORD.findall(sanitize(text)):
                if len(word) > 1:
                    counts[word.lower()] += 1
        print(f"  {len(seen)} articles, {len(counts)} distinct forms", end="\r", file=sys.stderr)
        time.sleep(0.2)  # be a good API citizen
    return len(seen), counts


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--articles", type=int, default=4000)
    parser.add_argument("--top", type=int, default=20_000)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sampled, counts = sample_intros(args.articles)
    ranked = counts.most_common(args.top)
    total = sum(counts.values())
    kept = sum(c for _, c in ranked)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            "# form<TAB>count — Narkamaŭka word-form frequency, most frequent first.\n"
            f"# Built by scripts/build_frequency_list.py from {sampled} random\n"
            "# be.wikipedia.org article INTROS (the only extracts the API batches), so the\n"
            "# register is definition-shaped: copulas, dates and place names are\n"
            "# over-represented relative to running prose. Text is CC BY-SA 4.0.\n"
            f"# {len(counts)} distinct forms over {total} tokens; "
            f"top {len(ranked)} kept, covering {kept / total:.1%} of tokens.\n"
        )
        for form, count in ranked:
            fh.write(f"{form}\t{count}\n")

    print(
        f"\n{sampled} articles → {len(counts)} distinct forms over {total} tokens; "
        f"wrote top {len(ranked)} ({kept / total:.1%} of tokens) → {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
