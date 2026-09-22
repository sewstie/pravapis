"""Coverage over a frequency list: every form lands in exactly one bucket.

The trap this guards against is quoting stem coverage as though it were a completeness
figure. Most Belarusian word forms are native and need no stem, so the buckets have to
stay separable — and the totals have to add up, or a form is being counted twice and the
percentages are inventions.
"""

from __future__ import annotations

from pathlib import Path

from pravapis.coverage import measure_coverage, read_frequency_list
from pravapis.pipeline import Converter


def test_buckets_partition_the_list(converter: Converter) -> None:
    forms = [("снег", 10), ("план", 5), ("сістэма", 3), ("і", 100), ("лапа", 2)]
    report = measure_coverage(forms, converter)
    total_types = (
        report.stem_loan.types
        + report.stem_native.types
        + report.lexicon.types
        + report.rule.types
        + report.untouched.types
    )
    total_tokens = (
        report.stem_loan.tokens
        + report.stem_native.tokens
        + report.lexicon.tokens
        + report.rule.tokens
        + report.untouched.tokens
    )
    assert total_types == report.forms == len(forms)
    assert total_tokens == report.occurrences == sum(c for _, c in forms)


def test_a_loan_stem_is_counted_as_a_loan_stem(converter: Converter) -> None:
    report = measure_coverage([("план", 1)], converter)
    assert report.stem_loan.types == 1
    assert report.untouched.types == 0


def test_a_native_guard_is_not_counted_as_loan_coverage(converter: Converter) -> None:
    """лапа matches a native stem: known about, but not evidence of loanword coverage."""
    report = measure_coverage([("лапа", 1)], converter)
    assert report.stem_native.types == 1
    assert report.stem_loan.types == 0


def test_a_word_only_a_rule_touches_needs_no_stem(converter: Converter) -> None:
    """снег is changed by assimilative softness, which is phonological, not etymological."""
    report = measure_coverage([("снег", 1)], converter)
    assert report.rule.types == 1
    assert report.stem.types == 0


def test_token_and_type_shares_differ_and_both_are_reported(converter: Converter) -> None:
    forms = [("і", 1000), ("план", 1)]  # one very frequent untouched word, one rare loan
    report = measure_coverage(forms, converter)
    types, tokens = report.share(report.stem_loan)
    assert types == 0.5  # half the vocabulary
    assert tokens < 0.01  # almost none of the text


def test_read_frequency_list_honours_the_limit(tmp_path: Path) -> None:
    path = tmp_path / "freq.tsv"
    path.write_text("# comment\nа\t3\nб\t2\nв\t1\n", encoding="utf-8")
    assert read_frequency_list(path) == [("а", 3), ("б", 2), ("в", 1)]
    assert read_frequency_list(path, limit=2) == [("а", 3), ("б", 2)]
