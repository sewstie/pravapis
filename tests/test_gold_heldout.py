"""The gold set must stay held out from everything that learns or looks things up."""

from __future__ import annotations

from pathlib import Path

import regex

from pravapis.metrics import PROVENANCES, read_gold
from pravapis.pipeline import Converter

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "eval" / "gold.tsv"

#: Code that builds the lexicon or trains the model must never open the gold set.
TRAINING_CODE = (
    ROOT / "src" / "pravapis" / "lexicon" / "builder.py",
    ROOT / "src" / "pravapis" / "disambiguate" / "train.py",
    ROOT / "src" / "pravapis" / "disambiguate" / "features.py",
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


def test_training_code_never_reads_the_recall_corpus() -> None:
    """The measurement corpora are the only evidence of *misses* this project has.

    Mine a stem out of `parallel.tsv` and the recall it reports becomes recall on the
    data it was fitted to — which is not a measurement of anything. Same argument as the
    gold set, one step further out: the gold set can be re-derived from the norm, while
    an independent attestation of a miss cannot be re-derived at all.
    """
    for path in TRAINING_CODE:
        body = path.read_text(encoding="utf-8").lower()
        # The filenames, not the words: builder.py legitimately discusses "parallel text"
        # as a technique, which is not the same as reading the measurement corpus.
        for name in ("parallel.tsv", "frequency_be.tsv", "data/corpora", "data\\corpora"):
            assert name not in body, f"{path} reads {name}"


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
        assert cols[3] in PROVENANCES, f"line {i}: provenance {cols[3]!r}"


def test_provenance_filters() -> None:
    from pravapis.metrics import read_gold_rows

    rows = read_gold_rows(GOLD)
    counts = {p: sum(r.provenance == p for r in rows) for p in ("uncertain", "hand_written")}
    assert len(read_gold(GOLD)) == len(rows) - counts["uncertain"]
    assert len(read_gold(GOLD, trusted_only=True)) == counts["hand_written"]
    assert len(read_gold(GOLD, trusted_only=True)) >= 500


# --- the headline guard ------------------------------------------------------------------
# Phase A grew the loanword rules from curated stem regexes to a data-driven stem
# inventory. The thing that must not move is the false-positive rate: a converter that
# changes a word it should not have is worse than one that leaves it alone. This is the
# gate CI runs on every change to data/lexicon/stems/.
def test_no_false_positives_on_the_trusted_gold_subset(converter: Converter) -> None:
    from pravapis.metrics import evaluate
    from pravapis.types import Orthography

    for direction in Orthography:
        report = evaluate(converter, read_gold(GOLD, trusted_only=True), direction)
        assert report.false_positives == 0, (
            f"{direction.value}: {report.false_positives} false positive(s) "
            f"out of {report.unchanged_words} words that should not change"
        )


def test_change_accuracy_does_not_regress(converter: Converter) -> None:
    """A floor, not a target: set below the measured 96.7% so noise does not fail CI,
    but high enough that losing a rule or a stem batch does."""
    from pravapis.metrics import evaluate
    from pravapis.types import Orthography

    for direction in Orthography:
        report = evaluate(converter, read_gold(GOLD, trusted_only=True), direction)
        assert report.change_accuracy >= 0.95, (direction.value, report.change_accuracy)
