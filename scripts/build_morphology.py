"""Build the -мент lemma table from GrammarDB.

    python scripts/build_morphology.py RELEASE-202601.zip

Taraškievica writes the suffix *-мент* as **-мэнт** when the base noun carries the stress
on it — дакумэ́нт, парлямэ́нт — and the э is inherited by everything derived from that base
even after the stress moves: манумэ́нт → манумэнта́льны, дакумэ́нт → дакумэнта́цыя. So the
fact to store is the **base noun**, not a per-form stress mark.

The bare colloquial noun *мент* is excluded, or any word starting мент- would match and
drag in *ментальны*, which is not derived from a -мент noun at all.

This script used to build three more tries for the genitive plural in -аў. That rule was
replaced by a whitelist in `data/lexicon/exceptions.tsv` — both forms are permissible for
many nouns, so a table that fires on all of them corrupts ordinary text — which took 752
KiB out of the deployment payload.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import marisa_trie

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "morphology"


def strip_stress(text: str) -> str:
    return text.replace("+", "").replace("`", "").replace("́", "")


def build(zip_path: Path) -> set[str]:
    ment: set[str] = set()
    with zipfile.ZipFile(zip_path) as zf:
        for name in sorted(zf.namelist()):
            if not name.endswith(".xml"):
                continue
            with zf.open(name) as fh:
                for _, elem in ET.iterparse(fh, events=("end",)):
                    if elem.tag != "Paradigm":
                        continue
                    is_noun = (elem.get("tag") or "").startswith("N")
                    lemma = strip_stress(elem.get("lemma") or "").lower()
                    # Base nouns in -мент. Taraškievica writes their suffix -мэнт, and the
                    # э is inherited by everything derived from them — манумэнт →
                    # манумэнтальны, дакумэнт → дакумэнтацыя — even where the stress has
                    # moved off the suffix. So the fact needed is the *base*, not the
                    # stress of the form in hand.
                    # The bare colloquial noun "мент" is excluded: keeping it would make
                    # any word starting мент- match, dragging in ментальны and менталітэт,
                    # which are not derived from a -мент noun at all.
                    if is_noun and lemma.endswith("мент") and lemma != "мент":
                        ment.add(lemma)
                    elem.clear()
    return ment


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("release", type=Path, help="a verified GrammarDB release zip")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    ment = build(args.release)
    args.out.mkdir(parents=True, exist_ok=True)

    marisa_trie.Trie(sorted(ment)).save(str(args.out / "ment_lemmas.marisa"))

    digest = hashlib.sha256(args.release.read_bytes()).hexdigest()
    (args.out / "SOURCE").write_text(
        f"release\t{args.release.stem}\nsha256\t{digest}\nment_lemmas\t{len(ment)}\n",
        encoding="utf-8",
    )
    total = sum(f.stat().st_size for f in args.out.glob("*.marisa"))
    print(f"-мент noun lemmas: {len(ment):,}")
    print(f"wrote {args.out}: {total / 1024:.0f} KiB of tries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
