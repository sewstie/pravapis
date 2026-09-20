"""Triage `gold_t2n.tsv` against the completed audit, so review time goes where it matters.

    python scripts/triage_gold_t2n.py

Every row in `gold_t2n.tsv` is a Taraškievica sentence plus a Narkamaŭka draft the
converter wrote. Reviewing 150 of those from scratch is slow — but each draft is made of
word changes the audit has *already* judged, one verdict per distinct change. Cross-
referencing the two says which sentences deserve reading and which do not:

    clean      every change in the row is marked `ok` in the audit
    flagged    the row contains a change marked `wrong` or `unsure`
    unjudged   the row contains a change the audit has no verdict for
    untouched  the converter changed nothing in this sentence

A `clean` row still needs a glance, because the audit can only judge changes that were
*made*. It says nothing about a word the converter should have changed and did not —
which is exactly what recall measures, and exactly why the gold set exists alongside the
audit. But a glance is not a reading, and that is the difference between an afternoon and
a weekend.

This script never writes a verdict or promotes a row. It sorts the queue.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.metrics import (  # noqa: E402
    OK,
    PROPOSED,
    UNSURE,
    WRONG,
    read_audit,
    read_gold_rows,
)
from pravapis.pipeline import Converter  # noqa: E402
from pravapis.types import Orthography  # noqa: E402

GOLD = ROOT / "data" / "eval" / "tarask" / "gold_t2n.tsv"
AUDIT = ROOT / "data" / "eval" / "tarask" / "audit.tsv"

CLEAN, FLAGGED, UNJUDGED, UNTOUCHED = "clean", "flagged", "unjudged", "untouched"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gold", type=Path, default=GOLD)
    ap.add_argument("--audit", type=Path, default=AUDIT)
    ap.add_argument(
        "--show",
        choices=[CLEAN, FLAGGED, UNJUDGED, UNTOUCHED, "all"],
        default=FLAGGED,
        help="which bucket to print in full (default: the ones needing attention)",
    )
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    verdicts = {(r.source, r.target): r.verdict for r in read_audit(args.audit).values()}
    if not verdicts:
        print(f"{args.audit} has no rows; run `pravapis audit` first", file=sys.stderr)
        return 2

    converter = Converter.from_config()
    rows = [r for r in read_gold_rows(args.gold) if r.provenance == PROPOSED]
    if not rows:
        print("no `proposed` rows left to triage — they have all been reviewed")
        return 0

    buckets: dict[str, list[tuple[str, list[str]]]] = {
        CLEAN: [],
        FLAGGED: [],
        UNJUDGED: [],
        UNTOUCHED: [],
    }
    for row in rows:
        result = converter.convert(row.taraskievica, Orthography.NARKAMAUKA)
        changes = [c for c in result.conversions if c.target != c.source]
        if not changes:
            buckets[UNTOUCHED].append((row.taraskievica, []))
            continue
        marks = [verdicts.get((c.source, c.target), "") for c in changes]
        detail = [
            f"{c.source} → {c.target} [{m or 'no verdict'}]"
            for c, m in zip(changes, marks, strict=True)
            if m != OK
        ]
        if any(m in (WRONG, UNSURE) for m in marks):
            buckets[FLAGGED].append((row.taraskievica, detail))
        elif any(m == "" for m in marks):
            buckets[UNJUDGED].append((row.taraskievica, detail))
        else:
            buckets[CLEAN].append((row.taraskievica, []))

    total = len(rows)
    print(f"{total} rows still marked `{PROPOSED}`\n")
    labels = {
        FLAGGED: "contain a change you marked wrong or unsure — read these",
        UNJUDGED: "contain a change the audit has no verdict for",
        CLEAN: "every change already marked ok — glance for MISSED changes only",
        UNTOUCHED: "converter changed nothing — check it should not have",
    }
    for name in (FLAGGED, UNJUDGED, CLEAN, UNTOUCHED):
        n = len(buckets[name])
        print(f"  {name:10} {n:4}  ({n / total:4.0%})  {labels[name]}")

    counts: Counter[str] = Counter()
    for _, detail in buckets[FLAGGED] + buckets[UNJUDGED]:
        for d in detail:
            counts[d] += 1
    if counts:
        print("\ndistinct changes driving the flagged rows:")
        for change, n in counts.most_common(15):
            print(f"  {n:3}  {change}")

    shown = [x for b in buckets.values() for x in b] if args.show == "all" else buckets[args.show]
    if shown:
        print(f"\n--- {args.show} ({min(len(shown), args.limit)} of {len(shown)}) ---")
        for sentence, detail in shown[: args.limit]:
            print(f"\n  T: {sentence}")
            for d in detail:
                print(f"     {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
