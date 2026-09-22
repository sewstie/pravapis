"""Record the current numbers as the floor the build will hold from now on.

    python scripts/update_baseline.py                  # dev only, the usual case
    python scripts/update_baseline.py --milestone      # also read the frozen test split
    python scripts/update_baseline.py --allow-regression "why"

The ratchet: each metric is stored at its best observed value, and
``tests/test_ratchet.py`` fails when a later measurement falls below it. Run this after
a review batch that improved something — the diff then shows exactly what the batch
bought, in the same commit that bought it.

A metric that went **down** is not recorded without ``--allow-regression`` and a reason,
and the reason is written into the file beside the number. That is the whole mechanism:
making a figure worse has to be a sentence somebody wrote, not a rerun.

``--milestone`` additionally measures the frozen test split. Leave it off for ordinary
batches. A test split read on every iteration is not frozen, it is a slow dev split, and
the number it eventually reports means nothing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.baseline import (  # noqa: E402
    BASELINE_NAME,
    compare,
    fingerprint,
    format_value,
    raised,
    read_baseline,
    today,
    write_baseline,
)
from pravapis.metrics import read_negative_set  # noqa: E402
from pravapis.pipeline import Converter  # noqa: E402
from pravapis.recall import measure_recall, read_parallel  # noqa: E402
from pravapis.types import Orthography  # noqa: E402

CORPUS: Final[Path] = ROOT / "data" / "corpora" / "parallel.tsv"
BASELINE: Final[Path] = ROOT / "data" / "eval" / BASELINE_NAME
NEGATIVE: Final[Path] = ROOT / "data" / "eval" / "negative.tsv"


def measure(split: str, corpus: Path, converter: Converter) -> dict[str, float]:
    """Both directions. The package ships both, so watching one watches half of it."""
    pairs = read_parallel(corpus, split)
    out: dict[str, float] = {}
    for direction, tag in (
        (Orthography.TARASKIEVICA, "n2t"),
        (Orthography.NARKAMAUKA, "t2n"),
    ):
        report = measure_recall(pairs, converter, split, direction)
        out[f"{split}_{tag}_recall"] = round(report.recall, 6)
        out[f"{split}_{tag}_precision"] = round(report.precision, 6)
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--out", type=Path, default=BASELINE)
    parser.add_argument(
        "--milestone",
        action="store_true",
        help="also measure the frozen test split; not for ordinary batches",
    )
    parser.add_argument(
        "--allow-regression",
        metavar="REASON",
        default=None,
        help="record a metric that fell, and write this reason beside it",
    )
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    converter = Converter.from_config()

    measured = measure("dev", args.corpus, converter)
    if args.milestone:
        measured |= measure("test", args.corpus, converter)
    measured["negative_set_forms"] = float(len(read_negative_set(NEGATIVE)))

    previous: dict[str, Any] = read_baseline(args.out) if args.out.is_file() else {}
    recorded: dict[str, float] = dict(previous.get("metrics", {}))

    fell = [m for m in compare(recorded, measured) if m.regressed]
    for metric in compare(recorded, measured):
        marker = "  REGRESSED" if metric.regressed else ""
        print(f"  {metric}{marker}")
    for name, value in measured.items():
        if name not in recorded:
            print(f"  {name}: {format_value(name, value)} (new)")

    if fell and args.allow_regression is None:
        print("\nNot written. These metrics fell:")
        for metric in fell:
            print(f"  {metric}")
        print(
            "\nFix them, or record the drop deliberately:\n"
            '  python scripts/update_baseline.py --allow-regression "why this is correct"'
        )
        return 1

    metrics = measured if fell else raised(recorded, measured)
    data: dict[str, Any] = {
        "corpus": {
            "path": str(args.corpus.relative_to(ROOT)).replace("\\", "/"),
            "fingerprint": fingerprint(args.corpus),
            "dev_pairs": len(read_parallel(args.corpus, "dev")),
        },
        "metrics": metrics,
        "updated": today(),
    }
    if fell:
        data["regression"] = {
            "reason": args.allow_regression,
            "metrics": [m.name for m in fell],
            "date": today(),
        }
    if not args.milestone and "test_recall" in recorded:
        # Keep the milestone figures rather than dropping them from the file just
        # because this run did not read the frozen split.
        for name in (n for n in recorded if n.startswith("test_")):
            if name in recorded:
                metrics.setdefault(name, recorded[name])

    write_baseline(args.out, data)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
