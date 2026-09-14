"""Build data/stress/ from a verified GrammarDB release zip.

    python scripts/build_stress_table.py RELEASE-202601.zip [--out data/stress]

GrammarDB marks stress with "+" after the stressed vowel (пла+н). Jakanne
(не → ня, без → бяз) is conditioned on whether the *next* word is stressed on
its first syllable, so the converter only needs one fact per word form:

    first_stressed.marisa   every form whose every reading carries exactly one
                            stress mark, on its first vowel

A form is left out — and the particle stays unchanged — when any reading puts
the stress elsewhere, when readings disagree (homographs: ма+е / мае+), or
when a reading has several marks (compounds with secondary stress). Common
nouns and proper names are keyed separately so Бу+дзе (a name) does not make
будзе ambiguous: proper_first_stressed.marisa holds the capitalised forms.

Only the verified release is accepted; the repository's data/ folder contains
unverified material by its own README. Data licence: CC BY-SA 4.0, GrammarDB by
Aleś Bułojčyk and Uładzimir Koščanka (see data/stress/README.md).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

import marisa_trie

ROOT = Path(__file__).resolve().parent.parent
VOWELS = frozenset("аеёіоуыэюяАЕЁІОУЫЭЮЯ")


def stress_positions(marked: str) -> tuple[int, ...]:
    """1-based vowel indices of the vowels followed by '+'."""
    out: list[int] = []
    n = 0
    for i, ch in enumerate(marked):
        if ch in VOWELS:
            n += 1
        elif ch == "+" and i > 0 and marked[i - 1] in VOWELS:
            out.append(n)
    return tuple(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("zip", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "stress")
    ap.add_argument("--release", default="RELEASE-202601")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    readings: dict[str, set[tuple[int, ...]]] = defaultdict(set)  # "c:word" / "p:Word"
    with zipfile.ZipFile(args.zip) as z:
        names = sorted(n for n in z.namelist() if n.endswith(".xml") and "/" not in n)
        if not names:
            print("no GrammarDB XML at the zip root; is this a release zip?", file=sys.stderr)
            return 2
        for name in names:
            with z.open(name) as fh:
                for _, el in ET.iterparse(fh, events=("end",)):
                    if el.tag == "Form":
                        text = (el.text or "").strip()
                        if text and "+" in text:
                            word = text.replace("+", "")
                            key = ("p:" + word) if word[:1].isupper() else ("c:" + word.lower())
                            readings[key].add(stress_positions(text))
                        el.clear()
                    elif el.tag == "Paradigm":
                        el.clear()
            print(f"{name}: {len(readings)} forms", file=sys.stderr)

    common: list[str] = []
    proper: list[str] = []
    stats = {"forms": len(readings), "first": 0, "other": 0, "homograph": 0, "multi_mark": 0}
    for key, rs in readings.items():
        if any(len(r) != 1 for r in rs):
            stats["multi_mark"] += 1
        elif len(rs) > 1:
            stats["homograph"] += 1
        elif next(iter(rs)) == (1,):
            stats["first"] += 1
            (common if key.startswith("c:") else proper).append(key[2:])
        else:
            stats["other"] += 1

    args.out.mkdir(parents=True, exist_ok=True)
    marisa_trie.Trie(common).save(str(args.out / "first_stressed.marisa"))
    marisa_trie.Trie(proper).save(str(args.out / "proper_first_stressed.marisa"))
    sha = hashlib.sha256(args.zip.read_bytes()).hexdigest()
    (args.out / "SOURCE").write_text(
        f"release\t{args.release}\nsha256\t{sha}\n"
        + "".join(f"{k}\t{v}\n" for k, v in stats.items())
        + f"common_first_stressed\t{len(common)}\nproper_first_stressed\t{len(proper)}\n",
        encoding="utf-8",
        newline="\n",
    )
    print(stats, f"common={len(common)} proper={len(proper)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
