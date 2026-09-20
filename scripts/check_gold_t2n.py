"""Flag `gold_t2n.tsv` rows whose Narkamaŭka side still looks like Taraškievica.

    python scripts/check_gold_t2n.py

The Narkamaŭka column is written by hand, and the easiest slip when correcting a draft is
to leave a Taraškievica form in it. The test: run that column through the T → N converter
again. Narkamaŭka in, Narkamaŭka out — if anything *changes*, the column still contains
something the converter reads as Taraškievica.

Pattern-matching for "Taraškievica markers" does not work here: a ь before a consonant is
assimilative in сьнег but perfectly ordinary in школьны, and no regex separates them. The
converter already knows the difference, so asking it is both tighter and free.

This is a **consistency check, not a judgement**. It cannot tell whether a conversion is
right — only that a row disagrees with the converter about its own Narkamaŭka side, which
is worth a human look either way. Where the row is right and the converter is wrong, that
is a finding too.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from pravapis.metrics import read_gold_rows  # noqa: E402
from pravapis.pipeline import Converter  # noqa: E402
from pravapis.types import Orthography  # noqa: E402

GOLD = ROOT / "data" / "eval" / "tarask" / "gold_t2n.tsv"
DERIVED = ROOT / "data" / "eval" / "gold.tsv"


def unsettled(converter: Converter, narkamauka: str) -> list[str]:
    """Words the T → N converter would still change in a supposedly Narkamaŭka string."""
    result = converter.convert(narkamauka, Orthography.NARKAMAUKA)
    return [f"{c.source} → {c.target}" for c in result.conversions if c.target != c.source]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gold", type=Path, default=GOLD)
    ap.add_argument(
        "--derived",
        action="store_const",
        const=DERIVED,
        dest="gold",
        help="check data/eval/gold.tsv instead",
    )
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    rows = read_gold_rows(args.gold)
    converter = Converter.from_config()
    suspect: list[tuple[int, str, list[str]]] = []
    identical = 0
    for i, row in enumerate(rows, 1):
        if row.narkamauka == row.taraskievica:
            identical += 1
        hits = unsettled(converter, row.narkamauka)
        if hits:
            suspect.append((i, row.narkamauka, hits))

    print(f"{len(rows)} rows · {identical} with both columns identical")
    print(f"{len(suspect)} rows the converter would change again\n")
    for i, text, hits in suspect[: args.limit]:
        print(f"  row {i}: {', '.join(sorted(set(hits)))}")
        print(f"     N: {text[:120]}")
    if len(suspect) > args.limit:
        print(f"\n  … and {len(suspect) - args.limit} more")
    return 1 if suspect else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
