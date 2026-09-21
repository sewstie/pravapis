"""The recall harness: what it counts, what it declines to count, and why a miss missed.

The numbers this produces are the ones a reader will quote, so the tests are mostly
about the *definitions*: that only in-scope differences reach the headline, that the
exclusions stay visible, and that each cause bucket means what its name says.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pravapis.pipeline import Converter
from pravapis.recall import (
    Change,
    MissCause,
    ParallelPair,
    classify,
    diff_pair,
    form_similarity,
    infer_alternations,
    measure_recall,
    read_parallel,
    write_misses,
)
from pravapis.scope import Scope, classify_scope
from pravapis.types import Orthography

N2T = Orthography.TARASKIEVICA


@pytest.mark.parametrize(
    ("source", "expected", "codes"),
    [
        ("снег", "сьнег", {"soft"}),
        ("сістэма", "сыстэма", {"i"}),
        ("сезон", "сэзон", {"e"}),
        ("Еўропа", "Эўропа", {"eu"}),
        ("план", "плян", {"l"}),
        ("годзе", "року", {"other"}),
    ],
)
def test_infer_alternations(source: str, expected: str, codes: set[str]) -> None:
    assert infer_alternations(source, expected) == codes


def test_a_change_needing_two_alternations_reports_both() -> None:
    assert "l" in infer_alternations("філасофія", "філязофія")


def test_similarity_is_measured_after_folding() -> None:
    assert form_similarity("снег", "сьнег") == 1.0
    assert form_similarity("плошчы", "пляцы") < 1.0


# --- diffing -----------------------------------------------------------------------
def test_diff_pair_finds_the_changed_tokens() -> None:
    pair = ParallelPair("снег і план", "сьнег і плян", "t", 0.5)
    tokens, changes = diff_pair(pair)
    assert tokens == 3
    assert [(c.source, c.expected) for c in changes] == [("снег", "сьнег"), ("план", "плян")]
    assert all(c.in_scope for c in changes)


def test_diff_pair_refuses_sentences_that_do_not_line_up() -> None:
    """A silent off-by-one would invent changes for every token after the first."""
    tokens, changes = diff_pair(ParallelPair("снег і план", "сьнег плян", "t", 0.5))
    assert (tokens, changes) == (0, [])


def test_diff_pair_labels_each_change_with_its_bucket() -> None:
    pair = ParallelPair("снег на плошчы завода", "сьнег на пляцы заводу", "t", 0.5)
    _, changes = diff_pair(pair)
    scopes = {c.source: c.scope for c in changes}
    assert scopes["снег"] is Scope.IN_SCOPE
    assert scopes["плошчы"] is Scope.NOT_ORTHOGRAPHIC
    assert scopes["завода"] is Scope.GRAMMATICAL


# --- cause attribution -------------------------------------------------------------
def _change(source: str, expected: str) -> Change:
    scope, reason = classify_scope(source, expected)
    return Change(
        source,
        expected,
        source,
        form_similarity(source, expected),
        infer_alternations(source, expected),
        scope,
        reason,
    )


def test_a_wrong_output_is_rule_wrong(converter: Converter) -> None:
    assert classify(_change("сістэма", "сыстэма"), "сыстэмa", converter).cause is (
        MissCause.RULE_WRONG
    )


def test_an_unknown_loan_stem_is_stem_absent(converter: Converter) -> None:
    miss = classify(_change("шмулацыя", "шмуляцыя"), "шмулацыя", converter)
    assert miss.cause is MissCause.STEM_ABSENT
    assert "no stem covers it" in miss.detail


def test_a_native_stem_blocking_a_needed_alternation_is_stem_untagged(
    converter: Converter,
) -> None:
    """лапа is deliberately classed native; a gold pair demanding ляпа means it is wrong."""
    miss = classify(_change("лапа", "ляпа"), "лапа", converter)
    assert miss.cause is MissCause.STEM_UNTAGGED
    assert "native" in miss.detail


# --- the report ---------------------------------------------------------------------
def test_only_in_scope_changes_reach_the_headline(converter: Converter) -> None:
    pairs = [
        ParallelPair("снег і план", "сьнег і плян", "t", 0.9),
        ParallelPair("на плошчы стаяў снег", "на пляцы стаяў сьнег", "t", 0.9),
    ]
    report = measure_recall(pairs, converter)
    assert report.by_scope[Scope.NOT_ORTHOGRAPHIC] == 1  # плошчы → пляцы, excluded
    assert report.in_scope == 3  # снег twice, план once
    assert report.changes == 4  # but every difference is still counted and shown


def test_a_perfect_corpus_scores_full_recall(converter: Converter) -> None:
    pairs = [ParallelPair("снег", converter.convert("снег", N2T).text, "t", 1.0)]
    report = measure_recall(pairs, converter)
    assert report.recall == 1.0
    assert report.misses == []


def test_identical_sides_make_no_recall_claim(converter: Converter) -> None:
    report = measure_recall([ParallelPair("сьнег", "сьнег", "t", 1.0)], converter)
    assert report.in_scope == 0
    assert report.recall == 0.0  # no evidence, not a perfect score


def test_the_headline_carries_an_interval(converter: Converter) -> None:
    report = measure_recall([ParallelPair("снег і план", "сьнег і плян", "t", 0.9)], converter)
    low, high = report.interval
    assert low <= report.recall <= high
    assert "[" in report.headline()


def test_out_of_scope_differences_are_not_misses(converter: Converter) -> None:
    """A word-choice difference must not appear in the work queue as something to fix."""
    report = measure_recall(
        [ParallelPair("на плошчы стаяў снег", "на пляцы стаяў сьнег", "t", 0.9)], converter
    )
    assert all(m.change.in_scope for m in report.misses)


def test_misses_file_lists_only_in_scope_work(converter: Converter, tmp_path: Path) -> None:
    report = measure_recall(
        [ParallelPair("на плошчы стаяў снег", "на пляцы стаяў сьнег", "t", 0.9)], converter
    )
    out = tmp_path / "misses.tsv"
    write_misses(report, out)
    body = out.read_text(encoding="utf-8")
    assert "in-scope miss" in body
    assert "пляцы" not in body


# --- splits ---------------------------------------------------------------------------
def _corpus(path: Path) -> Path:
    path.write_text(
        "# header\n"
        "снег\tсьнег\tА\t1\tА\t2\t0.900\ttrain\n"
        "план\tплян\tБ\t1\tБ\t2\t0.900\tdev\n"
        "сезон\tсэзон\tВ\t1\tВ\t2\t0.900\ttest\n",
        encoding="utf-8",
    )
    return path


def test_read_parallel_filters_by_split(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "parallel.tsv")
    assert len(read_parallel(corpus)) == 3
    assert [p.narkamauka for p in read_parallel(corpus, "dev")] == ["план"]
    assert [p.narkamauka for p in read_parallel(corpus, "test")] == ["сезон"]


def test_split_is_read_from_the_file_not_recomputed(tmp_path: Path) -> None:
    """What freezes the split: changing the hash function cannot move a frozen row."""
    corpus = tmp_path / "parallel.tsv"
    corpus.write_text("снег\tсьнег\tА\t1\tА\t2\t0.900\ttest\n", encoding="utf-8")
    (pair,) = read_parallel(corpus, "test")
    assert pair.split == "test"


def test_cli_reports_recall_for_one_split(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from pravapis.cli import app

    corpus = _corpus(tmp_path / "parallel.tsv")
    misses = tmp_path / "misses.tsv"
    result = CliRunner().invoke(
        app,
        ["eval", "--recall", "--corpus", str(corpus), "--split", "dev", "--misses", str(misses)],
    )
    assert result.exit_code == 0, result.output
    assert "in-scope" in result.output
    assert misses.is_file()


def test_cli_recall_says_what_to_do_when_there_is_no_corpus(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from pravapis.cli import app

    result = CliRunner().invoke(app, ["eval", "--recall", "--corpus", str(tmp_path / "absent.tsv")])
    assert result.exit_code == 2
