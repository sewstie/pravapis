"""Find the native words a loan stem would also match, using GrammarDB's lemma list.

    python scripts/check_stem_collisions.py RELEASE-202601.zip

`data/lexicon/stems/stems.tsv` matches by longest prefix, so a loan stem silently claims
every word that begins with it. `клас` claims *класці* ("to lay"), which is why a native
guard stem `класц` exists to beat it by one character. Finding those collisions by hand
is the part that does not scale — and it is the part that has to scale, because Phase A's
remaining work is growing the inventory from ~90 stems to thousands.

GrammarDB knows ~2M Belarusian word forms and their lemmas. This script asks it, for each
applied loan stem, which lemmas that stem prefixes, and reports the ones no guard covers.
The output is a review queue, not a patch: only a human can say whether *класці* is the
same lexeme as *клас* or a collision.

## Why this and not runtime lemma confirmation

The original phase D plan was to confirm at runtime that a matched word is an attested
form of the intended lexeme. Measured first: of 51 native guard stems, **3** change any
answer (`класц`, `падлог`, `клубок`); the other 48 are inert, held over from the
classifier era. A runtime confirmation layer would therefore add a data file, a lookup and
a deployment payload to solve a problem worth three rows. Build-time detection costs
nothing at runtime and directly serves the expansion that will eventually create the
problem.

Re-run it after every batch of mined stems.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.lexicon.stems import (  # noqa: E402
    StemEntry,
    WordClass,
    read_stem_sources,
)

DEFAULT_STEMS = ROOT / "data" / "lexicon" / "stems"


def lemmas(zip_path: Path) -> list[str]:
    """Every distinct GrammarDB lemma, stress marks stripped."""
    out: set[str] = set()
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.endswith(".xml"):
                continue
            with zf.open(name) as fh:
                for _, elem in ET.iterparse(fh, events=("end",)):
                    if elem.tag == "Paradigm":
                        lemma = (elem.get("lemma") or "").replace("+", "").replace("`", "")
                        if lemma:
                            out.add(lemma.lower())
                        elem.clear()
    return sorted(out)


def covered_by_guard(lemma: str, guards: list[str]) -> str | None:
    """The native guard that already beats a loan stem on ``lemma``, if any."""
    hits = [g for g in guards if lemma.startswith(g)]
    return max(hits, key=len) if hits else None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("release", type=Path, help="a verified GrammarDB release zip")
    ap.add_argument("--stems", type=Path, default=DEFAULT_STEMS)
    ap.add_argument("--max-per-stem", type=int, default=6, help="how many colliding lemmas to show")
    ap.add_argument(
        "--min-collisions",
        type=int,
        default=1,
        help="only report stems with at least this many uncovered lemmas",
    )
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    entries = read_stem_sources(args.stems)
    loan: list[StemEntry] = [
        e for e in entries if e.cls is WordClass.LOAN and e.applied and e.anchored
    ]
    guards = [e.stem for e in entries if e.cls is WordClass.NATIVE]
    print(f"{len(loan)} applied loan stems, {len(guards)} native guards", file=sys.stderr)

    all_lemmas = lemmas(args.release)
    print(f"{len(all_lemmas)} GrammarDB lemmas", file=sys.stderr)

    claimed: dict[str, list[str]] = defaultdict(list)
    for lemma in all_lemmas:
        # longest matching loan stem, mirroring StemIndex's longest-match rule
        hits = [e.stem for e in loan if lemma.startswith(e.stem)]
        if hits:
            claimed[max(hits, key=len)].append(lemma)

    total_uncovered = 0
    rows: list[tuple[int, str, list[str]]] = []
    for stem, hit_lemmas in claimed.items():
        uncovered = [
            lemma
            for lemma in hit_lemmas
            if lemma != stem and covered_by_guard(lemma, guards) is None
        ]
        if len(uncovered) >= args.min_collisions:
            rows.append((len(uncovered), stem, uncovered))
            total_uncovered += len(uncovered)

    rows.sort(reverse=True)
    print(f"\n# {len(rows)} loan stems claim lemmas no guard covers ({total_uncovered} lemmas)")
    print("# Review each: a lemma that is NOT the same lexeme needs a native guard row")
    print("# in stems.tsv, long enough to beat the loan stem.\n")
    for n, stem, uncovered in rows:
        shown = ", ".join(uncovered[: args.max_per_stem])
        more = f" … +{n - args.max_per_stem}" if n > args.max_per_stem else ""
        print(f"{stem}\t{n}\t{shown}{more}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
