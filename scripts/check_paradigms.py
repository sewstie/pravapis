"""Find lemmas the converter treats inconsistently across their own inflected forms.

    python scripts/check_paradigms.py RELEASE-202601.zip --limit 40

A conversion is a fact about a *stem*, so it must hold for every form of a lemma. When
пенсія became пэнсія but пенсіі stayed пенсіі, the bug was visible without knowing which
spelling is right: one paradigm cannot be half converted. That is what this checks.

For each GrammarDB paradigm it takes the longest prefix common to every form — the part
of the stem the inflection never touches — converts each form, and asks what that shared
prefix became. Every form must answer the same. пенсія → пэнсі-, пенсіі → пенсі- is a
contradiction no ground truth is needed to see.

Anchoring on the shared prefix is what keeps the check honest. Comparing whole-form edits
instead flags гасціць, whose forms гасціла and гашчу legitimately differ: the сц cluster
that softens is simply absent from гашчу. Those forms share only "га", so the prefix test
passes over them, while пенсія's forms share "пенсі" and are held to it.

No gold, no human ruling. It cannot say a paradigm is wrong, only that it is not
self-consistent — which for a stem-based converter is already a defect.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.pipeline import Converter  # noqa: E402
from pravapis.types import Method, Orthography  # noqa: E402

#: GrammarDB tags the part of speech in the first character.
PART_OF_SPEECH: dict[str, str] = {
    "N": "noun",
    "A": "adjective",
    "V": "verb",
    "P": "participle",
    "M": "numeral",
    "S": "pronoun",
    "R": "adverb",
    "C": "conjunction",
    "I": "preposition",
    "E": "particle",
    "Y": "interjection",
    "Z": "predicative",
    "W": "parenthetic",
    "F": "fragment",
    "K": "abbreviation",
}


def strip_stress(text: str) -> str:
    return text.replace("+", "").replace("`", "").replace("́", "")


def shared_prefix(forms: list[str]) -> str:
    """The longest prefix every form has in common — the stem the endings never touch."""
    first, last = forms[0], forms[-1]  # forms arrive sorted; these two bound the rest
    n = 0
    while n < len(first) and n < len(last) and first[n] == last[n]:
        n += 1
    return first[:n]


def prefix_image(source: str, target: str, upto: int) -> str:
    """What ``source[:upto]`` became in ``target``.

    The conversion can change length (снег → сьнег), so the boundary is carried across
    with an alignment rather than by index.
    """
    if source == target:
        return source[:upto]
    out = 0
    for op, i1, i2, j1, j2 in SequenceMatcher(None, source, target).get_opcodes():
        if i2 <= upto:
            out = j2
            continue
        if i1 >= upto:
            break
        # the boundary falls inside this block. An equal block maps character for
        # character, so the offset carries straight across; any other block has no
        # internal alignment, so it is taken whole.
        out = j1 + (upto - i1) if op == "equal" else j2
        break
    return target[:out]


def paradigms(zip_path: Path):
    with zipfile.ZipFile(zip_path) as zf:
        for name in sorted(zf.namelist()):
            if not name.endswith(".xml"):
                continue
            with zf.open(name) as fh:
                for _, elem in ET.iterparse(fh, events=("end",)):
                    # Only ever clear a finished Paradigm. Form elements end *before*
                    # their parent does, so clearing them here empties the paradigm
                    # before it can be read.
                    if elem.tag != "Paradigm":
                        continue
                    lemma = strip_stress(elem.get("lemma") or "")
                    forms = {strip_stress(f.text or "") for f in elem.iter("Form")}
                    forms = {f for f in forms if f and " " not in f}
                    if lemma and forms:
                        yield lemma, elem.get("tag") or "", sorted(forms)
                    elem.clear()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("release", type=Path)
    ap.add_argument("--limit", type=int, default=40, help="how many lemmas to print")
    ap.add_argument("--min-forms", type=int, default=3)
    ap.add_argument("--min-stem", type=int, default=4)
    ap.add_argument("--tag", default="", help="only paradigms whose tag starts with this")
    ap.add_argument("--out", type=Path, help="write every split paradigm to this TSV")
    ap.add_argument(
        "--lexicon-only",
        action="store_true",
        help=(
            "only paradigms the LEXICON split. Rules are allowed to treat forms "
            "differently — метр → мэтар inserts its а only word-finally, and the "
            "geminate ньн softens only before a front vowel — so a rule-driven "
            "split is usually correct. A lexicon-driven one means the entry covers "
            "some forms of the lemma and not others, which is always a defect."
        ),
    )
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    converter = Converter.from_config()
    convert = converter.convert
    T = Orthography.TARASKIEVICA

    split: list[tuple[str, str, str, dict[str, list[str]]]] = []
    scanned = skipped = 0

    for lemma, tag, forms in paradigms(args.release):
        if len(forms) < args.min_forms or not tag.startswith(args.tag):
            continue
        stem = shared_prefix(forms)
        if len(stem) < args.min_stem:
            skipped += 1
            continue
        scanned += 1
        images: dict[str, list[str]] = {}
        methods: set[str] = set()
        for f in forms:
            result = convert(f, T)
            img = prefix_image(f, result.text, len(stem))
            if img != stem:
                methods.update(c.method for c in result.conversions if c.source != c.target)
            images.setdefault(img, []).append(f)
        if len(images) > 1 and (not args.lexicon_only or Method.LEXICON in methods):
            split.append((lemma, tag, stem, images))

    print(
        f"scanned {scanned:,} paradigms; skipped {skipped:,} with a shared stem < {args.min_stem}"
    )
    print(f"\n=== {len(split):,} paradigms whose forms disagree about their own stem ===\n")

    kinds = Counter(PART_OF_SPEECH.get(tag[:1], f"other ({tag[:1]})") for _, tag, _, _ in split)
    width = max(len(k) for k in kinds) if kinds else 0
    print("by part of speech:")
    for kind, n in kinds.most_common():
        print(f"  {n:6,}  {kind:{width}}")

    print(f"\nfirst {min(args.limit, len(split))}:\n")
    for lemma, tag, stem, images in split[: args.limit]:
        print(f"  {lemma}  [{tag[:4]}]  stem {stem!r}")
        for img, fs in sorted(images.items(), key=lambda kv: -len(kv[1])):
            print(f"      {img!r:16} ← {', '.join(fs[:4])}")
        print()

    if args.out:
        with args.out.open("w", encoding="utf-8") as fh:
            fh.write("lemma\ttag\tstem\tconverted_to\tconverting_forms\tunchanged_forms\n")
            for lemma, tag, stem, images in split:
                same = images.get(stem, [])
                for img, fs in images.items():
                    if img == stem:
                        continue
                    fh.write(f"{lemma}\t{tag}\t{stem}\t{img}\t{','.join(fs)}\t{','.join(same)}\n")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
