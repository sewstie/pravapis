"""Dump every word that breaks on N→T→N, grouped by the stages that fired.

    python scripts/mine_roundtrip.py [corpus.txt] [out.tsv]

Defaults: data/eval/roundtrip_corpus.txt → data/eval/roundtrip_failures.tsv.
The corpus is unlabelled Narkamaŭka text and deliberately *not* the gold set,
so fixing what this finds does not tune the converter on its own test data.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pravapis.metrics import write_round_trip_failures
from pravapis.pipeline import Converter

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str]) -> int:
    corpus = Path(argv[0]) if argv else ROOT / "data" / "eval" / "roundtrip_corpus.txt"
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "data" / "eval" / "roundtrip_failures.tsv"
    lines = [
        ln.strip()
        for ln in corpus.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    n_words, failures, ordered = write_round_trip_failures(
        lines, Converter.from_config(), out, corpus.name
    )
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    print(f"{len(failures)} failures / {n_words} words → {out}")
    for group, items in ordered:
        print(f"{len(items):5d}  {group}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
