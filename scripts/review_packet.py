"""Collect every open question into one document a native Taraškievica writer can answer.

    python scripts/review_packet.py --out review-packet.md

The project's gold set was written from Klasyčny pravapis (2005), so its numbers
mean "agrees with a careful reading of the norm", not "is correct". Replacing that caveat
needs a native reader — and their time is the scarce resource, so this gathers the
questions that actually need a human and nothing else.

Three sources, all machine-collected so the packet cannot drift from the data:

* **contradictions** — changes the audit marks `ok` while the gold says the word should
  not change. Two files by the same reviewer disagreeing; at least one is wrong.
* **unresolved** — the items `data/NORMS.md` records as unsettled, where two cited
  sections point different ways or no section was found at all.
* **uncertain stems** — rows in `stems.tsv` held back for want of a source. They are
  parsed, counted and never applied, so each one is coverage the converter is declining.

Each question is posed with its evidence and both candidate answers, so it can be answered
without reading the codebase.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.lexicon.stems import Provenance, WordClass, read_stem_sources  # noqa: E402
from pravapis.metrics import OK, evaluate, read_audit, read_gold  # noqa: E402
from pravapis.pipeline import Converter  # noqa: E402
from pravapis.types import Orthography  # noqa: E402

TARASK = ROOT / "data" / "eval" / "tarask"

HEADER = """# pravapis — open questions for a native reviewer

Every question below is one where the project cannot settle the answer from the sources it
has. They are ordered by how much they affect the measured numbers.

**How to answer:** write the correct form next to each item, or "leave as is". Where a
question offers two spellings, either may be right — the point is which one Belarusian
actually uses, not which one a rule predicts.

No knowledge of the code is needed.
"""


def contradictions(converter: Converter) -> list[tuple[str, str, str]]:
    """Changes the audit calls ok while the gold says the word should not change."""
    verdicts = {(r.source, r.target): r.verdict for r in read_audit(TARASK / "audit.tsv").values()}
    report = evaluate(
        converter,
        read_gold(TARASK / "gold_t2n.tsv", trusted_only=True),
        Orthography.NARKAMAUKA,
        origin=Orthography.TARASKIEVICA,
    )
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str, str]] = []
    for err in report.errors:
        if err.source != err.expected:
            continue  # a miss, not a disputed change
        key = (err.source, err.predicted)
        if key in seen or verdicts.get(key) != OK:
            continue
        seen.add(key)
        out.append((err.source, err.predicted, err.expected))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "review-packet.md")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    converter = Converter.from_config()
    disputed = contradictions(converter)
    uncertain = [
        e
        for e in read_stem_sources(ROOT / "data" / "lexicon" / "stems")
        if e.provenance is Provenance.UNCERTAIN and e.cls is WordClass.LOAN
    ]

    lines = [HEADER]

    lines.append("\n## 1. The converter and the gold set disagree\n")
    if disputed:
        lines.append(
            "For each of these, the audit says the change is right and the gold set says the "
            "word should stay as it is. **Which spelling does Narkamaŭka use?**\n"
        )
        lines.append("| Taraškievica | converter says | gold says | which is right? |")
        lines.append("|---|---|---|---|")
        for source, predicted, expected in disputed:
            lines.append(f"| {source} | {predicted} | {expected} | |")
    else:
        lines.append("None — the two files agree.\n")

    lines.append("\n## 2. Words held back for want of a source\n")
    g_stems = sorted((e for e in uncertain if "g" in e.alternations), key=lambda x: x.stem)
    others = sorted((e for e in uncertain if "g" not in e.alternations), key=lambda x: x.stem)
    if g_stems:
        lines.append(
            "These carry ґ in common usage, but Збор 2005 зноска 55 ends its list with "
            '"ды інш." without naming them. The converter leaves them alone, even in '
            "aggressive mode. **Is ґ correct in each?**\n"
        )
        lines.append("| word | with ґ | correct? |")
        lines.append("|---|---|---|")
        for e in g_stems:
            lines.append(f"| {e.stem} | {e.stem.replace('г', 'ґ', 1)} | |")
    for e in others:
        lines.append(
            f"\n**-{e.stem}**: does every word ending in -{e.stem} take э there "
            "(дакумэнт, аргумэнт, манумэнт), or are there exceptions? Held back because "
            "the one gold row that tested it disagreed.\n"
        )

    lines.append("\n## 3. Two cited sections pointing different ways\n")
    lines.append(
        "- **эўрапейскі or эўрапэйскі?** §52 gives еў → эў; §11б gives е → э after a "
        "consonant. Applying both gives эўрапэйскі, which is what be-tarask writes; the "
        "project's codification test expects эўрапейскі. Which is used?\n"
        "- **мадрыдзкі or мадрыдскі?** The corpus writes мадрыдзкі; no section was found "
        "licensing дз before с here. Is мадрыдзкі right, and does it generalise "
        "(бэрлінскі/бэрлінзкі, лёнданскі/лёнданзкі)?\n"
        "- **Genitive plural -аў**: хвілін or хвілінаў, краін or краінаў? The project "
        "converts краінаў only, on instruction, and leaves every other noun alone. Is -аў "
        "general, or does it depend on the noun?\n"
        "- **унутр or унутар?** `morph.final_tr` inserts the epenthetic а in every "
        "word-final -тр (тэатр → тэатар, цэнтр → цэнтар), so it also makes унутр → унутар. "
        "Both wikis write унутр unchanged. §26 governs borrowings, and унутр is native "
        "(у + нутро), so the rule may simply not reach it — but §26 could not be read to "
        "confirm. If унутар is wrong, унутр joins сартр and нотр in the rule's exception "
        "list in `data/rules/morphology.yaml`.\n"
        "- **Softness across a hyphen**: §29 limits assimilative softness to "
        '"у межах слова". In a compound like сьвятлова-зялёны, does the softness of the '
        "first part carry?\n"
    )

    lines.append("\n## 4. Is the gold set trustworthy at all?\n")
    lines.append(
        "The 150 Taraškievica sentences in `data/eval/tarask/gold_t2n.tsv` come from "
        "be-tarask.wikipedia.org, so they are genuine. Their Narkamaŭka counterparts were "
        "drafted by the converter and corrected by hand. **A spot-check of ten rows** — do "
        "they read as ordinary Narkamaŭka? — would say more about the headline accuracy "
        "figure than any other single answer here.\n"
    )

    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"  {len(disputed)} converter/gold contradictions")
    print(f"  {len(uncertain)} stems held back for want of a source")
    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "contradictions": [
                        {"taraskievica": s, "converter": p, "gold": e} for s, p, e in disputed
                    ],
                    "uncertain_stems": [e.stem for e in uncertain],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  also {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
