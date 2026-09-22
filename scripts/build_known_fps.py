"""Regenerate `data/eval/known_fps.tsv` from the dev split, keeping the causes.

    python scripts/build_known_fps.py            # rewrite the file in place
    python scripts/build_known_fps.py --check    # print what would change, write nothing

The word forms are measured; the **cause column is not**. Nothing here can tell a wiki
that simply is not normalised from a rule that overreaches — that is a reading of the
text against Збор 2005, and a human does it once per form. So a form already in the file
keeps the cause it was given, and a form that is new arrives as `reference_deviates`
with a `REVIEW` note on it, which is the common case and also the one a reviewer must
confirm rather than assume.

`tests/test_ratchet.py` is the gate: any dev false positive missing from this file fails
the build. This script is how you answer it — run it, then read the new rows and correct
the causes. Running it is never enough on its own.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.config import Config  # noqa: E402
from pravapis.metrics import FP_DIRECTIONS, KnownFalsePositive, read_known_fps  # noqa: E402
from pravapis.pipeline import Converter  # noqa: E402
from pravapis.recall import measure_recall, read_parallel  # noqa: E402

OUT: Path = ROOT / "data" / "eval" / "known_fps.tsv"

HEADER = """\
# direction<TAB>source<TAB>target<TAB>rule<TAB>cause<TAB>note
#
# Every false positive the converter produces on the **dev** split of
# data/corpora/parallel.tsv: a word the two wikis spelled identically, that the
# converter changed anyway. One row per word form per direction.
#
# This file is a gate, not a report. tests/test_ratchet.py fails on any dev false
# positive whose word form is not listed here, independent of what aggregate precision
# does — a batch that fixes four and introduces four others moves no percentage and
# must still fail. Adding a row is a deliberate act: it says someone read the sentence
# and decided the converter is not what needs fixing.
#
# Regenerate with `python scripts/build_known_fps.py`, then review the new rows. The
# script measures the forms; it cannot assign a cause.
#
# direction  n2t = Narkamaŭka -> Taraškievica, t2n = the reverse
# source     the word form as the corpus writes it, lowercased
# target     what the converter produced, lowercased
# rule       the rule id that fired, or `lexicon` when the change came from a table
# cause      one of: reference_deviates, proper_noun, rule_unsourced, lexicon_overreach
#            (defined in pravapis.metrics.FP_CAUSES)
#
# Measured on the dev split only. The test split is read at releases, never in CI.
"""


def measure() -> list[tuple[str, str, str, str]]:
    """``(direction, source, target, rule)`` for every dev false positive."""
    converter = Converter.from_config(None)
    corpus = Config.default().lexicon.parent / "corpora" / "parallel.tsv"
    pairs = read_parallel(corpus, "dev")
    seen: dict[tuple[str, str], tuple[str, str, str, str]] = {}
    for tag, direction in FP_DIRECTIONS.items():
        report = measure_recall(pairs, converter, "dev", direction)
        for source, target, rule in report.false_positives:
            key = (tag, source.lower())
            # First occurrence wins: a form that reaches two targets is one form to
            # review, and the row carries the first target it was seen producing.
            # `rule` arrives stringified, so a change that came from a table rather
            # than a rule reaches here as the literal "None".
            fired = rule if rule and rule != "None" else "lexicon"
            seen.setdefault(key, (tag, source.lower(), target.lower(), fired))
    return [seen[k] for k in sorted(seen)]


def render(measured: list[tuple[str, str, str, str]], existing: list[KnownFalsePositive]) -> str:
    known = {row.key: row for row in existing}
    lines = [HEADER]
    for direction, source, target, rule in measured:
        previous = known.get((direction, source))
        cause = previous.cause if previous else "reference_deviates"
        note = previous.note if previous else "REVIEW: cause not yet confirmed"
        lines.append("\t".join((direction, source, target, rule, cause, note)))
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="print the diff, write nothing")
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    existing = read_known_fps(OUT) if OUT.is_file() else []
    measured = measure()
    payload = render(measured, existing)

    was = {row.key for row in existing}
    now = {(d, s) for d, s, _, _ in measured}
    for key in sorted(now - was):
        print(f"  new    {key[0]}  {key[1]}")
    for key in sorted(was - now):
        print(f"  stale  {key[0]}  {key[1]}  (no longer a false positive — drop the row)")

    if args.check:
        print(f"\n{len(measured)} dev false positives; {OUT} not written (--check)")
        return 1 if (now - was) else 0

    OUT.write_bytes(payload.encode("utf-8"))
    print(f"\n{OUT}: {len(measured)} rows")
    if now - was:
        print("Review the rows marked REVIEW and give each a cause before committing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
