"""Draft an independent T → N gold set from the Taraškievica corpus, for human review.

    python scripts/propose_gold_t2n.py --sentences 150

Samples sentences from `data/eval/tarask/corpus.tsv` (genuine be-tarask text), runs the
converter on each, and writes both sides to `data/eval/tarask/gold_t2n.tsv` with
provenance **`proposed`**.

`proposed` rows are never scored. That is the whole point: a converter proposal scored
against the converter returns 100% by construction and would say nothing. The rows exist
so a human has something to correct rather than something to write from scratch —
correcting a draft is perhaps five times faster than composing, and Narkamaŭka is the
standard the reviewer already writes natively.

To promote a row, read it, fix the Narkamaŭka side if it is wrong, and change
`proposed` to `hand_written`. Only then does it count. Rows left `proposed` are reported
as unreviewed.

The file declares `# origin: taraskievica`, so `pravapis eval` labels → narkamauka as
accuracy and → taraskievica as self-consistency — the mirror image of gold.tsv.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.metrics import PROPOSED, GoldRow, read_corpus, read_gold_rows  # noqa: E402
from pravapis.pipeline import Converter  # noqa: E402
from pravapis.types import Orthography  # noqa: E402

OUT = ROOT / "data" / "eval" / "tarask" / "gold_t2n.tsv"
CORPUS = ROOT / "data" / "eval" / "tarask" / "corpus.tsv"

HEADER = """# narkamauka<TAB>taraskievica<TAB>source<TAB>provenance
# origin: taraskievica
#   The Taraškievica side is the original: genuine text from be-tarask.wikipedia.org,
#   written by Taraškievica writers and not derived from any Narkamaŭka source. So
#   T → N scored here is accuracy — the figure data/eval/gold.tsv cannot give, because
#   its Taraškievica side was derived from its Narkamaŭka side.
#
# HELD OUT. Never read by lexicon building, stem mining, or model training
# (enforced by tests/test_gold_heldout.py).
#
# provenance `proposed` = the Narkamaŭka side is a converter draft, NOT reviewed, and is
# never scored. Read the row, correct the Narkamaŭka side, then change `proposed` to
# `hand_written` to make it count.
#
# Text CC BY-SA 4.0, be-tarask.wikipedia.org contributors — see README.md.
"""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sentences", type=int, default=150)
    ap.add_argument("--corpus", type=Path, default=CORPUS)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--seed", type=int, default=42, help="sampling seed, for reproducibility")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    corpus = read_corpus(args.corpus)
    if not corpus:
        print(f"{args.corpus} has no sentences", file=sys.stderr)
        return 2

    # Keep rows a human has already touched; only ever add to the file.
    existing: dict[str, GoldRow] = {}
    if args.out.is_file():
        existing = {r.taraskievica: r for r in read_gold_rows(args.out)}
    print(f"{len(existing)} rows already present", file=sys.stderr)

    pool = [row for row in corpus if row.sentence not in existing]
    random.Random(args.seed).shuffle(pool)
    chosen = pool[: max(0, args.sentences - len(existing))]

    converter = Converter.from_config()
    lines: list[str] = []
    for row in existing.values():
        lines.append(
            f"{row.narkamauka}\t{row.taraskievica}\t{row.source}\t{row.provenance or PROPOSED}"
        )
    for row in chosen:
        narkamauka = converter.convert(row.sentence, Orthography.NARKAMAUKA).text
        source = f"betarask:{row.article}@{row.revid}"
        lines.append(f"{narkamauka}\t{row.sentence}\t{source}\t{PROPOSED}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(HEADER + "\n".join(lines) + "\n", encoding="utf-8")

    reviewed = sum(1 for r in existing.values() if r.provenance and r.provenance != PROPOSED)
    print(
        f"wrote {args.out}: {len(lines)} rows "
        f"({len(chosen)} new proposals, {reviewed} already reviewed)"
    )
    print("Review them, then change `proposed` to `hand_written` to make a row count.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
