"""The gold set must stay held out from everything that learns or looks things up."""

from __future__ import annotations

from pathlib import Path

import regex

from belnorm.metrics import read_gold

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "eval" / "gold.tsv"

#: Code that builds the lexicon or trains the model must never open the gold set.
TRAINING_CODE = (
    ROOT / "src" / "belnorm" / "lexicon" / "builder.py",
    ROOT / "src" / "belnorm" / "disambiguate" / "train.py",
    ROOT / "src" / "belnorm" / "disambiguate" / "features.py",
    ROOT / "scripts" / "build_lexicon.py",
    ROOT / "scripts" / "train_model.py",
    ROOT / "scripts" / "align_corpora.py",
)


def _norm(s: str) -> str:
    return regex.sub(r"\s+", " ", s.strip().lower())


def test_gold_is_large_enough() -> None:
    assert len(read_gold(GOLD)) >= 500


def test_training_code_never_reads_gold() -> None:
    for path in TRAINING_CODE:
        assert "gold" not in path.read_text(encoding="utf-8").lower(), path


def test_no_gold_sentence_in_training_contexts() -> None:
    gold = {_norm(n) for n, _ in read_gold(GOLD)}
    contexts: set[str] = set()
    for line in (ROOT / "data" / "eval" / "ambiguous.tsv").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        cols = line.split("\t")
        if len(cols) >= 3:
            contexts.add(_norm(cols[2]))
    assert not gold & contexts


def test_gold_rows_are_well_formed() -> None:
    for i, line in enumerate(GOLD.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("#") or not line.strip():
            continue
        cols = line.split("\t")
        assert len(cols) == 4, f"line {i}: expected 4 columns"
        assert cols[3] in {"annotated", "uncertain", "reviewed"}, f"line {i}: status {cols[3]!r}"
