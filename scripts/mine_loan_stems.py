"""Propose loan stems from a GrammarDB release, ranked, for human review.

    python scripts/mine_loan_stems.py RELEASE-202601.zip > candidates.tsv

GrammarDB gives lemmas and full paradigms for ~2M Narkamaŭka word forms. Western
borrowings are not marked in it, but they are strongly signalled by their
derivational morphology: *-цыя*, *-ізм*, *-энт*, *-тар*, *-лёг*, *-граф* and friends
are Greco-Latin suffixes with no native Belarusian source. This script finds lemmas
carrying one, works out which alternations §55.1 / §67 / §11б would have something to
say about, and prints them as `stems.tsv` rows with provenance `derived`.

**The output is a proposal, not data.** `derived` rows are applied by the converter,
so read a batch before you paste it in, and demote anything you are unsure of to
`uncertain`. Rows whose stem is already present (in either class) are dropped, so
re-running after a review round only shows what is new.

The ranking is by paradigm size — the number of word forms the stem would affect —
so an hour of review buys as much coverage as possible.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.lexicon.stems import read_stem_sources  # noqa: E402
from pravapis.rules.loanwords import e_to_eh, i_to_y, palatalize_l  # noqa: E402

#: Greco-Latin derivational suffixes with no native Belarusian source. A lemma ending
#: in one of these is a borrowing with high precision — which is the whole claim the
#: stem inventory needs to make.
LOAN_SUFFIXES: Final[tuple[str, ...]] = (
    "цыя",
    "сія",
    "зія",
    "ізм",
    "ызм",
    "іст",
    "ыст",
    "энт",
    "ент",
    "ант",
    "тар",
    "тур",
    "ура",
    "лог",
    "лаг",
    "графія",
    "граф",
    "метр",
    "метрыя",
    "номія",
    "скоп",
    "тэка",
    "фон",
    "ацыя",
    "іka",
    "ічны",
    "ычны",
    "альны",
    "ярны",
    "іўны",
    "ыўны",
)

#: Suffixes that look Greco-Latin but sit on native stems often enough to be useless.
SUFFIX_BLOCKLIST: Final[frozenset[str]] = frozenset({"ічны", "ычны", "альны"})


def lemmas_with_counts(zip_path: Path) -> Counter[str]:
    """Every GrammarDB lemma, counted by how many word forms its paradigm holds."""
    counts: Counter[str] = Counter()
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.endswith(".xml"):
                continue
            with zf.open(name) as fh:
                for _, elem in ET.iterparse(fh, events=("end",)):
                    if elem.tag != "Paradigm":
                        continue
                    lemma = (elem.get("lemma") or "").replace("+", "").replace("`", "").lower()
                    if lemma:
                        counts[lemma] += sum(1 for _ in elem.iter("Form"))
                    elem.clear()
    return counts


def alternations_for(stem: str) -> str:
    """Which alternations would actually change this stem."""
    codes: list[str] = []
    if palatalize_l(stem) != stem:
        codes.append("l")
    if i_to_y(stem) != stem:
        codes.append("i")
    if e_to_eh(stem) != stem:
        codes.append("e")
    return ",".join(codes) if codes else "-"


def stem_of(lemma: str) -> str:
    """Strip the inflectional ending so the row covers the whole paradigm."""
    for ending in ("ыя", "ія", "ая", "ы", "і", "а", "я", "ь"):
        if lemma.endswith(ending) and len(lemma) - len(ending) >= 4:
            return lemma[: -len(ending)]
    return lemma


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("release", type=Path, help="a verified GrammarDB release zip")
    ap.add_argument("--limit", type=int, default=500, help="how many candidates to print")
    ap.add_argument(
        "--stems",
        type=Path,
        default=ROOT / "data" / "lexicon" / "stems",
        help="existing inventory, to skip stems already reviewed",
    )
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    known = {e.stem for e in read_stem_sources(args.stems)} if args.stems.exists() else set()
    counts = lemmas_with_counts(args.release)

    proposals: list[tuple[int, str, str, str]] = []
    seen: set[str] = set()
    for lemma, forms in counts.items():
        suffix = next(
            (s for s in LOAN_SUFFIXES if lemma.endswith(s) and s not in SUFFIX_BLOCKLIST),
            None,
        )
        if suffix is None:
            continue
        stem = stem_of(lemma)
        if stem in known or stem in seen:
            continue
        codes = alternations_for(stem)
        if codes == "-":
            continue  # nothing would change; the row would never fire
        seen.add(stem)
        proposals.append((forms, stem, codes, suffix))

    proposals.sort(reverse=True)
    print("# stem\tclass\talternations\tsource\tprovenance")
    print(f"# {len(proposals)} candidates; showing {min(args.limit, len(proposals))}")
    print("# REVIEW BEFORE USE — `derived` rows are applied by the converter.")
    for forms, stem, codes, suffix in proposals[: args.limit]:
        print(
            f"{stem}\tloan\t{codes}\tЗбор 2005 §55.1/§67/§11б\tderived\t# -{suffix}, {forms} forms"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
