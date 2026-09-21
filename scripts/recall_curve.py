"""What would accepting the next N stems actually buy? Measure it before accepting any.

    python scripts/recall_curve.py --steps 0,25,50,100,165

A stem inventory grows one review session at a time, and the only honest way to decide
whether another session is worth it is to know the shape of the curve: if the first
fifty stems move recall eight points and the next hundred move it two, the answer is to
stop and go find a rule instead. Guessing that from the miner's `impact` column does not
work, because impact counts tokens the stem *touches*, not changes it gets right, and
because the candidates overlap heavily — `амерык`, `амерыкан` and `амерыканск` are three
rows and one fact.

Nothing is written to `data/`. Each point builds a throwaway stems directory in a
temporary folder, points a `Config` at it and measures, so the real inventory is never
touched and the answer costs nothing to be wrong about.

The candidates are taken in the file's own order, which is verdict first and impact
second, so point N is "the N stems a reviewer would have reached by then" rather than
an arbitrary subset. Only `supported` rows are used: the refuted ones are refuted.

Measured on the **dev** split. Test stays frozen; this is a decision aid, not a result.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.config import Config  # noqa: E402
from pravapis.lexicon.stems import SCHEMA_ID  # noqa: E402
from pravapis.pipeline import Converter  # noqa: E402
from pravapis.recall import measure_recall, read_parallel  # noqa: E402
from pravapis.scope import format_interval  # noqa: E402

CANDIDATES: Final[Path] = ROOT / "data" / "review" / "stem_candidates.tsv"
INVENTORY: Final[Path] = ROOT / "data" / "lexicon" / "stems"
CORPUS: Final[Path] = ROOT / "data" / "corpora" / "parallel.tsv"


def supported(path: Path) -> list[tuple[str, ...]]:
    """The first six columns of every `supported` candidate, in file order."""
    rows: list[tuple[str, ...]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        f = line.split("\t")
        if len(f) >= 7 and f[6] == "supported":
            rows.append(tuple(f[:6]))
    return rows


def measure(extra: list[tuple[str, ...]], split: str, corpus: Path) -> tuple[int, int, int, int]:
    """``(hits, in_scope, wrong, stems)`` with ``extra`` appended to the inventory."""
    with tempfile.TemporaryDirectory() as tmp:
        stems_dir = Path(tmp) / "stems"
        stems_dir.mkdir()
        shutil.copy(INVENTORY / "stems.tsv", stems_dir / "stems.tsv")
        if extra:
            body = "".join("\t".join(row) + "\n" for row in extra)
            (stems_dir / "trial.tsv").write_text(
                f"#!schema {SCHEMA_ID}\n"
                "#!columns stem\tclass\talternations\tsource\tprovenance\ttarget\n"
                "# Throwaway. Written by scripts/recall_curve.py, never under data/.\n" + body,
                encoding="utf-8",
            )
        config = Config.default().model_copy(update={"stems": stems_dir})
        converter = Converter.from_config(config)
        report = measure_recall(read_parallel(corpus, split), converter, split)
        return report.in_scope_hits, report.in_scope, report.wrong, len(extra)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--split", default="dev")
    parser.add_argument("--steps", default="0,25,50,100,200", help="comma-separated stem counts")
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    rows = supported(args.candidates)
    steps = sorted({min(int(s), len(rows)) for s in args.steps.split(",") if s.strip()})
    print(f"{len(rows)} supported candidate(s); measuring on split {args.split!r}\n")
    print(f"{'stems added':>12}  {'in-scope recall [95% CI]':>28}  {'precision':>22}")

    for n in steps:
        hits, total, wrong, added = measure(rows[:n], args.split, args.corpus)
        made = hits + wrong
        print(f"{added:>12}  {format_interval(hits, total):>28}  {format_interval(hits, made):>22}")
    print(
        "\nBoth columns are Wilson 95%. Recall that rises while precision falls is a stem "
        "catching\nnative vocabulary, not a stem doing its job — read data/eval/negative.tsv next."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
