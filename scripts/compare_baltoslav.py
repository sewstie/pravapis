"""Measure how far this converter agrees with baltoslav.eu on Narkamaŭka → Taraškievica.

    python scripts/compare_baltoslav.py --sentences 200

Both tools convert the same Narkamaŭka text; the output is compared word by word.

**Agreement is not accuracy.** baltoslav is another implementation, not ground truth, and
the two disagree in both directions — some of its output follows conventions the 2005
codification does not, and some of ours is rules it has not implemented. A disagreement is
a lead to look at, never proof that either side is wrong. The project's accuracy figures
come from `data/eval/`, where a human has ruled on each case; this number says something
different and smaller: how much of the problem two independent implementations see the
same way.

Sentences come from the Narkamaŭka side of `data/eval/gold.tsv` — authentic site text —
so neither converter has seen them as training data.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.metrics import read_gold_rows  # noqa: E402
from pravapis.pipeline import Converter  # noqa: E402
from pravapis.tokenize import tokenize  # noqa: E402
from pravapis.types import Orthography, TokenKind  # noqa: E402

ENDPOINT = "https://baltoslav.eu/tar/index.php?mova=en"
TEXTAREA = re.compile(r"<textarea[^>]*>(.*?)</textarea>", re.S)
USER_AGENT = "pravapis-compare/0.1 (https://github.com/sewstie/pravapis; research)"
MAX_CHARS = 3500  # the page caps its textarea; stay well under


def baltoslav(text: str) -> str:
    """POST one batch of newline-joined sentences and return its Taraškievica."""
    # the form is <form name="ularz"> with a single textarea named "t"
    body = urllib.parse.urlencode({"t": text, "mova": "en"}).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as fh:
        html = fh.read().decode("utf-8", "replace")
    areas = TEXTAREA.findall(html)
    if not areas:
        raise RuntimeError("no <textarea> in the response; the page layout may have changed")
    # the last textarea holds the output; the first echoes the input
    import html as html_mod

    return html_mod.unescape(areas[-1]).strip()


def words(text: str) -> list[str]:
    return [t.text for t in tokenize(text) if t.kind is TokenKind.WORD]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sentences", type=int, default=200)
    ap.add_argument("--show", type=int, default=25, help="how many disagreements to print")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    rows = read_gold_rows(ROOT / "data" / "eval" / "gold.tsv")
    sentences = [r.narkamauka for r in rows if r.narkamauka][: args.sentences]
    converter = Converter.from_config()

    batches: list[list[str]] = [[]]
    size = 0
    for sentence in sentences:
        if size + len(sentence) > MAX_CHARS and batches[-1]:
            batches.append([])
            size = 0
        batches[-1].append(sentence)
        size += len(sentence) + 1

    agree = disagree = skipped = 0
    diffs: Counter[tuple[str, str, str]] = Counter()
    for n, batch in enumerate(batches, 1):
        theirs = baltoslav("\n".join(batch)).splitlines()
        if len(theirs) != len(batch):
            skipped += len(batch)
            print(f"  batch {n}: line count changed, skipped", file=sys.stderr)
            continue
        for source, other in zip(batch, theirs, strict=True):
            ours = converter.convert(source, Orthography.TARASKIEVICA).text
            a, b, src = words(ours), words(other), words(source)
            if not (len(a) == len(b) == len(src)):
                skipped += 1
                continue
            for s, x, y in zip(src, a, b, strict=True):
                if x == y:
                    agree += 1
                else:
                    disagree += 1
                    diffs[(s, x, y)] += 1
        print(f"  batch {n}/{len(batches)}", file=sys.stderr)
        time.sleep(1.0)

    total = agree + disagree
    if not total:
        print("nothing compared", file=sys.stderr)
        return 1
    print(f"\n{len(sentences)} sentences · {total} words compared · {skipped} skipped")
    print(f"agreement: {agree / total:.2%}  ({agree}/{total})")
    print("\ntop disagreements (source → ours | baltoslav):")
    for (src, ours_w, theirs_w), count in diffs.most_common(args.show):
        print(f"  {count:4}  {src:22} → {ours_w:22} | {theirs_w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
