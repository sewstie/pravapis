"""Mine candidate lexicon pairs from two line-parallel files.

    python scripts/align_corpora.py narkamauka.txt taraskievica.txt > candidates.tsv

Only words that differ are emitted, with a count, most frequent first. Pairs a
rule already explains are dropped so the output is exactly the lexical residue.
Review by hand before adding anything to data/lexicon/.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from pravapis.config import Config
from pravapis.lexicon.builder import align_corpora
from pravapis.rules.engine import RuleEngine
from pravapis.types import Orthography


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    cfg = Config.default()
    engine = RuleEngine.from_yaml(*cfg.rules)
    counts: Counter[tuple[str, str]] = Counter()
    for nark, tarask in align_corpora(Path(argv[0]), Path(argv[1])):
        if engine.apply(nark, Orthography.TARASKIEVICA)[0] == tarask:
            continue
        counts[(nark, tarask)] += 1
    for (nark, tarask), n in counts.most_common():
        print(f"{nark}\t{tarask}\t{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
