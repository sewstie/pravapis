"""Freeze the words the converter must leave alone, from what both wikis already agree on.

    python scripts/build_negative_set.py

Recall says what the converter fails to change. Precision needs the opposite evidence:
words it must **not** change. Those are harder to come by, because nobody writes down
the words that stay the same — but the parallel corpus records them implicitly. Where an
aligned sentence pair has the same token on both sides, a Narkamaŭka writer and a
Taraškievica writer independently spelled that word identically. Nothing is due there,
and a converter that changes it anyway is wrong.

This is the set a growing lexicon threatens. Every stem accepted widens what matches, and
the failure mode is never "the stem does nothing" — it is a stem that quietly catches
native vocabulary three commits later. `клас-` is right for кляса and wrong for класці,
and the only thing standing between them is a native guard somebody remembered to add.
The gate makes forgetting fail the build instead of the next release.

## Three rules, all load-bearing

**Train split only.** dev and test stay clean, so the recall and precision numbers
measured on them are still measurements rather than a report on what was fitted.

**A pinned row is never dropped.** Rebuilding is additive. Otherwise regenerating would
launder the exact regression the file exists to catch: a bad stem makes `беларусі`
change, the rebuild quietly removes `беларусі` for changing, and the gate goes green on
a converter that is now wrong. A pinned row leaves only by hand, in a commit that says
why — and while it is there and failing, the build stays red.

**Contested forms are dropped.** be-tarask is community-written and not uniformly
Taraškievica: an author may simply have left a loanword unconverted, which looks exactly
like agreement. So a form is only kept if the corpus *never* shows it converted anywhere
else — if both `амерыканскі` and `амэрыканскі` are attested, the agreement was an
accident and the form says nothing. Forms are grouped by `pravapis.scope.neutral_fold`,
which is the same equality test the aligner uses for "same word, different spelling".

Output: ``data/eval/negative.tsv``, checked by ``tests/test_negative_set.py``.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.metrics import read_negative_set  # noqa: E402
from pravapis.pipeline import Converter  # noqa: E402
from pravapis.recall import read_parallel  # noqa: E402
from pravapis.scope import neutral_fold  # noqa: E402
from pravapis.tokenize import tokenize  # noqa: E402
from pravapis.types import Orthography, TokenKind  # noqa: E402

OUT: Final[Path] = ROOT / "data" / "eval" / "negative.tsv"
CORPUS: Final[Path] = ROOT / "data" / "corpora" / "parallel.tsv"

#: How often the two wikis must agree on a form before it is pinned. One agreement can
#: be one author's oversight; the threshold is what separates evidence from coincidence.
MIN_ATTESTATIONS: Final[int] = 2

HEADER = """# form\tattestations\tnote
#
# THE NEGATIVE SET: words the converter must leave unchanged, N -> T.
#
# Built by scripts/build_negative_set.py from the TRAIN split of
# data/corpora/parallel.tsv. Each form is one both wikis wrote identically at an
# aligned position, at least {minimum} times, and which the corpus never shows
# converted anywhere else. dev and test are untouched, so the numbers measured on
# them stay measurements.
#
# This is a PRECISION gate, and it exists because of the lexicon. Every stem accepted
# widens what matches, and a stem that catches native vocabulary is the one failure
# mode that a recall number cannot see. Checked by tests/test_negative_set.py.
#
# A row here is evidence, not doctrine: be-tarask is community-written, and a form
# attested identically may still be one the 2005 code would change. If a change is
# genuinely right, delete the row and say why in the commit -- do not weaken the test.
"""


def agreements(corpus: Path, split: str) -> tuple[Counter[str], set[str]]:
    """``(form -> times both wikis wrote it, folds the corpus shows converted)``."""
    agreed: Counter[str] = Counter()
    variants: dict[str, set[str]] = defaultdict(set)

    for pair in read_parallel(corpus, split):
        n_tokens = [t.text for t in tokenize(pair.narkamauka) if t.kind is TokenKind.WORD]
        t_tokens = [t.text for t in tokenize(pair.taraskievica) if t.kind is TokenKind.WORD]
        if len(n_tokens) != len(t_tokens):
            continue
        for n, t in zip(n_tokens, t_tokens, strict=True):
            n_low, t_low = n.lower(), t.lower()
            variants[neutral_fold(n_low)] |= {n_low, t_low}
            if n_low == t_low:
                agreed[n_low] += 1

    contested = {fold for fold, forms in variants.items() if len(forms) > 1}
    return agreed, contested


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--split", default="train")
    parser.add_argument("--min", type=int, default=MIN_ATTESTATIONS, dest="minimum")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    agreed, contested = agreements(args.corpus, args.split)
    print(f"{len(agreed)} form(s) both wikis wrote identically in split {args.split!r}")
    print(f"{len(contested)} fold group(s) the corpus shows converted somewhere — dropped")

    kept = sorted(
        (form, n)
        for form, n in agreed.items()
        if n >= args.minimum and neutral_fold(form) not in contested
    )
    print(f"{len(kept)} form(s) attested >= {args.minimum} times and never converted")

    # A form the converter already changes is not pinnable: pinning it would freeze a
    # failing assertion into the build. It is reported instead, because it is either a
    # real false positive or a row that should not be in the set.
    #
    # A form ALREADY pinned is never dropped, though, however the converter behaves now.
    # Dropping it would launder the regression it is there to catch: a bad stem makes
    # беларусі change, the next rebuild quietly removes беларусі for changing, and the
    # gate goes green on a converter that is now wrong. A pinned row leaves this file
    # only by hand, in a commit that says why.
    converter = Converter.from_config()
    pinned = {form for form, _ in read_negative_set(args.out)} if args.out.is_file() else set()
    counts = {form: n for form, n in kept}
    for form in pinned:
        counts.setdefault(form, args.minimum)

    changes = {
        form: converter.convert(form, Orthography.TARASKIEVICA).text
        for form in sorted(counts)
        if converter.convert(form, Orthography.TARASKIEVICA).text.lower() != form
    }
    regressions = {f: g for f, g in changes.items() if f in pinned}
    fresh = {f: g for f, g in changes.items() if f not in pinned}

    if regressions:
        print(f"\n!! {len(regressions)} PINNED form(s) the converter now changes:")
        for form, got in list(regressions.items())[:20]:
            print(f"  {form} -> {got}")
        print("   Kept. tests/test_negative_set.py fails until this is fixed, or until")
        print("   the row is deleted by hand with a reason.")
    if fresh:
        print(f"\n{len(fresh)} new form(s) the converter changes — not pinned, review:")
        for form, got in list(fresh.items())[:20]:
            print(f"  {form} -> {got}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    written = sorted(form for form in counts if form not in fresh)
    with args.out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(HEADER.format(minimum=args.minimum))
        for form in written:
            fh.write(f"{form}\t{counts[form]}\t\n")

    print(f"\nwrote {len(written)} form(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
