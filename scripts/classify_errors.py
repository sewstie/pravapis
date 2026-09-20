"""Bucket the remaining evaluation errors by what would actually fix each one.

    python scripts/classify_errors.py

An error list says what is wrong. It does not say what to *build*, and those are different
questions: twenty errors can look like one problem and be five, of which four need data or
a decision and one needs architecture. Guessing wrong there is how a project spends a
month on machinery that fixes two words.

So each error is sorted by its remedy, mechanically:

``disputed``     the audit says this change is right and the gold says the word should not
                 change. A decision, not code — and already collected by
                 ``scripts/review_packet.py``.
``gold``         the expected form is not a Belarusian word (a typo, or the wrong
                 language). The yardstick needs fixing, not the converter.
``stem``         the expected form differs from ours only by an alternation the stem
                 inventory already knows how to apply. One TSV row each.
``morphology``   the ending changes, not just the stem: a case, number or gender shift.
                 This is the tier-2 gap — it needs Taraškievica paradigms, which GrammarDB
                 does not have.
``vocabulary``   a different *word*, not a different spelling of the same one. No
                 orthography rule reaches these; they need a synonym list.
``unresolved``   named in data/NORMS.md as unsettled.

The point is the counts. Build for the biggest bucket, and only if it is the kind of thing
you can build at all.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.metrics import OK, ErrorCase, evaluate, read_audit, read_gold  # noqa: E402
from pravapis.pipeline import Converter  # noqa: E402
from pravapis.tokenize import BELARUSIAN_LETTERS  # noqa: E402
from pravapis.types import Orthography  # noqa: E402

TARASK = ROOT / "data" / "eval" / "tarask"

DISPUTED, GOLD, STEM, MORPHOLOGY, VOCABULARY, UNRESOLVED = (
    "disputed",
    "gold",
    "stem",
    "morphology",
    "vocabulary",
    "unresolved",
)

#: words data/NORMS.md records as unsettled
UNRESOLVED_WORDS = ("мадрыдз", "эўрапэй", "еўрапэй")

#: letters that differ only by an alternation the inventory already applies
_ALTERNATION_PAIRS = (("і", "ы"), ("е", "э"), ("л", "ль"), ("г", "ґ"))


def _is_belarusian(word: str) -> bool:
    return bool(word) and all(c.lower() in BELARUSIAN_LETTERS for c in word)


def _same_skeleton(a: str, b: str) -> bool:
    """Do two words differ only in letters an alternation swaps, with the ending intact?"""
    if len(a) != len(b):
        return False
    for x, y in zip(a.lower(), b.lower(), strict=True):
        if x == y:
            continue
        if not any({x, y} == set(pair) for pair in _ALTERNATION_PAIRS):
            return False
    return True


def classify(err: ErrorCase, disputed: set[tuple[str, str]]) -> str:
    if (err.source, err.predicted) in disputed:
        return DISPUTED
    if not _is_belarusian(err.expected):
        return GOLD
    if any(w in err.source.lower() or w in err.expected.lower() for w in UNRESOLVED_WORDS):
        return UNRESOLVED
    if _same_skeleton(err.source, err.expected):
        return STEM
    # A shared long prefix with a different tail is an ending change; a different start
    # is a different word.
    shared = 0
    for x, y in zip(err.source.lower(), err.expected.lower(), strict=False):
        if x != y:
            break
        shared += 1
    if shared >= max(3, min(len(err.source), len(err.expected)) - 3):
        return MORPHOLOGY
    return VOCABULARY


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gold", type=Path, default=TARASK / "gold_t2n.tsv")
    ap.add_argument("--audit", type=Path, default=TARASK / "audit.tsv")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    converter = Converter.from_config()
    verdicts = {(r.source, r.target): r.verdict for r in read_audit(args.audit).values()}
    disputed = {k for k, v in verdicts.items() if v == OK}

    report = evaluate(
        converter,
        read_gold(args.gold, trusted_only=True),
        Orthography.NARKAMAUKA,
        origin=Orthography.TARASKIEVICA,
    )
    buckets: dict[str, list[ErrorCase]] = {}
    for err in report.errors:
        kind = classify(err, disputed if err.source == err.expected else set())
        buckets.setdefault(kind, []).append(err)

    total = sum(len(v) for v in buckets.values())
    print(f"{total} remaining errors, by what would fix each\n")
    remedy = {
        DISPUTED: "a decision — see scripts/review_packet.py",
        GOLD: "fix the gold row; the expected form is not Belarusian",
        STEM: "one row in data/lexicon/stems/stems.tsv",
        MORPHOLOGY: "tier-2 morphology: needs Taraškievica paradigms (do not have)",
        VOCABULARY: "a synonym list: a different word, not a different spelling",
        UNRESOLVED: "named unsettled in data/NORMS.md",
    }
    for kind, _ in Counter({k: len(v) for k, v in buckets.items()}).most_common():
        errs = buckets[kind]
        print(f"  {kind:12} {len(errs):3}  ({len(errs) / total:4.0%})  {remedy[kind]}")
        for e in errs:
            print(f"                    {e.source} → {e.predicted}   want {e.expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
