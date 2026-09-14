"""Dump every word that breaks on N→T→N, grouped by the stages that fired.

    python scripts/mine_roundtrip.py [corpus.txt] [out.tsv]

Defaults: data/eval/roundtrip_corpus.txt → data/eval/roundtrip_failures.tsv.
The corpus is unlabelled Narkamaŭka text and deliberately *not* the gold set,
so fixing what this finds does not tune the converter on its own test data.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from belnorm.metrics import RoundTripFailure, round_trip_failures
from belnorm.pipeline import Converter

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str]) -> int:
    corpus = Path(argv[0]) if argv else ROOT / "data" / "eval" / "roundtrip_corpus.txt"
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "data" / "eval" / "roundtrip_failures.tsv"
    lines = [
        ln.strip()
        for ln in corpus.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    n_words, failures = round_trip_failures(lines, Converter.from_config())
    groups: dict[str, list[RoundTripFailure]] = defaultdict(list)
    for f in failures:
        groups[f.group].append(f)
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            f"# {len(failures)} failing words of {n_words} "
            f"({1 - len(failures) / n_words if n_words else 0:.2%} word round trip) "
            f"from {corpus.name}\n"
        )
        fh.write("# group (N→T stage | T→N stage)\tsource\ttaraskievica\tback\tsentence\n")
        for group, items in ordered:
            for f in items:
                fh.write(f"{group}\t{f.source}\t{f.there}\t{f.back}\t{f.sentence}\n")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    print(f"{len(failures)} failures / {n_words} words → {out}")
    for group, items in ordered:
        print(f"{len(items):5d}  {group}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
