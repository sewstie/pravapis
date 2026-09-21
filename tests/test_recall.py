"""The recall harness: what it counts, what it refuses to count, and why a miss missed.

The numbers this produces are the ones a reader will quote, so the tests are mostly
about the *definitions* — that a word-choice difference is not counted as a converter
failure, that recall is reported as a bound, and that each cause bucket means what its
name says.
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


@pytest.mark.parametrize(
    ("source", "expected", "codes"),
    [
        ("снег", "сьнег", {"soft"}),
        ("сістэма", "сыстэма", {"i"}),
        ("сезон", "сэзон", {"e"}),
        ("Еўропа", "Эўропа", {"eu"}),
        ("Еуропа", "Эуропа", {"eu"}),
        ("план", "плян", {"l"}),
        ("годзе", "року", {"other"}),
    ],
)
def test_infer_alternations(source: str, expected: str, codes: set[str]) -> None:
    assert infer_alternations(source, expected) == codes


def test_a_change_needing_two_alternations_reports_both() -> None:
    assert infer_alternations("сістэма", "сыстэма") <= {"i", "e", "other"}
    assert "l" in infer_alternations("філасофія", "філязофія")


def test_similarity_separates_a_respelling_from_a_different_word() -> None:
    assert form_similarity("снег", "сьнег") > 0.8
    assert form_similarity("плошчы", "пляцы") < 0.7


# --- diffing -----------------------------------------------------------------------
def test_diff_pair_finds_the_changed_tokens() -> None:
    pair = ParallelPair("снег і план", "сьнег і плян", "t", 0.5)
    tokens, changes = diff_pair(pair)
    assert tokens == 3
    assert [(c.source, c.expected) for c in changes] == [("снег", "сьнег"), ("план", "плян")]


def test_diff_pair_refuses_sentences_that_do_not_line_up() -> None:
    """A silent off-by-one would invent changes for every token after the first."""
    tokens, changes = diff_pair(ParallelPair("снег і план", "сьнег плян", "t", 0.5))
    assert (tokens, changes) == (0, [])


# --- cause attribution -------------------------------------------------------------
def _change(source: str, expected: str) -> Change:
    return Change(
        source,
        expected,
        source,
        form_similarity(source, expected),
        infer_alternations(source, expected),
    )


def test_a_word_choice_difference_is_not_a_converter_failure(converter: Converter) -> None:
    miss = classify(_change("плошчы", "пляцы"), "плошчы", converter)
    assert miss.cause is MissCause.NOT_ORTHOGRAPHIC


def test_a_wrong_output_is_rule_wrong(converter: Converter) -> None:
    miss = classify(_change("сістэма", "сыстэма"), "сыстэмa", converter)
    assert miss.cause is MissCause.RULE_WRONG


def test_an_unknown_loan_stem_is_stem_absent(converter: Converter) -> None:
    """The alternation is needed, and nothing in the inventory could have licensed it."""
    miss = classify(_change("шмулацыя", "шмуляцыя"), "шмулацыя", converter)
    assert miss.cause is MissCause.STEM_ABSENT
    assert "no stem covers it" in miss.detail


def test_a_native_stem_blocking_a_needed_alternation_is_stem_untagged(
    converter: Converter,
) -> None:
    """лапа is deliberately classed native; if a gold pair demanded ляпа, the fact is wrong."""
    miss = classify(_change("лапа", "ляпа"), "лапа", converter)
    assert miss.cause is MissCause.STEM_UNTAGGED
    assert "native" in miss.detail


def test_every_miss_cause_is_reachable_and_named(converter: Converter) -> None:
    causes = {
        classify(_change(s, e), got, converter).cause
        for s, e, got in [
            ("плошчы", "пляцы", "плошчы"),
            ("сістэма", "сыстэма", "сыстэмa"),
            ("лапа", "ляпа", "лапа"),
        ]
    }
    assert causes == {
        MissCause.NOT_ORTHOGRAPHIC,
        MissCause.RULE_WRONG,
        MissCause.STEM_UNTAGGED,
    }


# --- the report ---------------------------------------------------------------------
def test_recall_is_reported_as_a_bound(converter: Converter) -> None:
    """Strict counts every diff; orthographic counts only respellings. Strict <= orthographic."""
    pairs = [
        ParallelPair("снег і план", "сьнег і плян", "t", 0.9),
        ParallelPair("на плошчы стаяў снег", "на пляцы стаяў сьнег", "t", 0.7),
    ]
    report = measure_recall(pairs, converter)
    assert report.changes > report.orthographic_changes  # the word-choice diff was excluded
    assert report.strict_recall <= report.orthographic_recall


def test_a_perfect_corpus_scores_full_recall(converter: Converter) -> None:
    pairs = [ParallelPair("снег", converter.convert("снег", _T).text, "t", 1.0)]
    report = measure_recall(pairs, converter)
    assert report.strict_recall == 1.0
    assert report.misses == []


def test_identical_sides_produce_no_changes_and_no_recall_claim(converter: Converter) -> None:
    report = measure_recall([ParallelPair("сьнег", "сьнег", "t", 1.0)], converter)
    assert report.changes == 0
    assert report.strict_recall == 0.0  # no evidence, not a perfect score


def test_misses_file_groups_by_cause(converter: Converter, tmp_path: Path) -> None:
    report = measure_recall(
        [ParallelPair("на плошчы стаяў снег", "на пляцы стаяў сьнег", "t", 0.7)], converter
    )
    out = tmp_path / "misses.tsv"
    write_misses(report, out)
    body = out.read_text(encoding="utf-8")
    assert "# cause\tsource\texpected" in body
    assert "not_orthographic" in body


def test_read_parallel_skips_comments(tmp_path: Path) -> None:
    path = tmp_path / "parallel.tsv"
    path.write_text("# header\nснег\tсьнег\tТытул\t1\tТытул\t2\t0.900\n", encoding="utf-8")
    (pair,) = read_parallel(path)
    assert (pair.narkamauka, pair.taraskievica, pair.similarity) == ("снег", "сьнег", 0.9)


def test_cli_reports_recall_and_writes_the_misses_file(tmp_path: Path) -> None:
    """The wiring: `pravapis eval --recall` runs without a gold file and names both bounds."""
    from typer.testing import CliRunner

    from pravapis.cli import app

    corpus = tmp_path / "parallel.tsv"
    corpus.write_text(
        "# header\nна плошчы стаяў снег\tна пляцы стаяў сьнег\tТ\t1\tТ\t2\t0.750\n",
        encoding="utf-8",
    )
    misses = tmp_path / "misses.tsv"
    result = CliRunner().invoke(
        app, ["eval", "--recall", "--corpus", str(corpus), "--misses", str(misses)]
    )
    assert result.exit_code == 0, result.output
    assert "strict" in result.output and "orthographic" in result.output
    assert misses.is_file()


def test_cli_recall_says_what_to_do_when_there_is_no_corpus(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from pravapis.cli import app

    result = CliRunner().invoke(app, ["eval", "--recall", "--corpus", str(tmp_path / "absent.tsv")])
    assert result.exit_code == 2


from pravapis.types import Orthography as _O  # noqa: E402

_T = _O.TARASKIEVICA
