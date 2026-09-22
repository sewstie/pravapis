"""The data boundary: everything that changes the output must have a case behind it.

`conformance/cases.jsonl` is the contract. Anything the converter reads that no case
exercises is *outside* the contract — a port can get it wrong, pass the corpus, and be
wrong in production. `pravapis conformance --coverage` is the audit that says so, and
these tests are what keep the audit itself honest: a coverage check that cannot fail is
a coverage check nobody should trust.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from pravapis.conformance import (
    EXEMPT_DATA,
    EXEMPT_RULES,
    Case,
    build_corpus,
    coverage,
)
from pravapis.pipeline import Converter
from tests.conftest import DATA_DIR


@pytest.fixture(scope="module")
def cases() -> list[Case]:
    built, _ = build_corpus(DATA_DIR)
    return built


def test_the_shipped_data_boundary_is_clean(cases: list[Case], converter: Converter) -> None:
    """The gate itself. Every rule, lexicon table and data file is covered or exempt."""
    report = coverage(DATA_DIR, cases, converter)
    assert report.ok, "uncovered:\n  " + "\n  ".join(str(gap) for gap in report.gaps)


def test_every_rule_in_the_data_is_accounted_for(cases: list[Case], converter: Converter) -> None:
    report = coverage(DATA_DIR, cases, converter)
    uncovered = {name for name, count in report.rules.items() if count == 0}
    assert uncovered <= set(EXEMPT_RULES), (
        f"rules with no conformance case and no exemption: {sorted(uncovered - set(EXEMPT_RULES))}"
    )


def test_the_case_context_rule_is_covered(cases: list[Case], converter: Converter) -> None:
    """A regression guard on the gap this audit found.

    `lex.case_context` picks a different Taraškievica ending depending on the preposition
    before the word (сталіца Германіі → Нямеччыны, у Германіі → Нямеччыне). It changes
    the output and had no case at all until the audit said so.
    """
    report = coverage(DATA_DIR, cases, converter)
    assert report.rules["lex.case_context"] > 0
    assert report.data_files["lexicon/case/ambiguous.tsv"] > 0


def test_removing_a_case_opens_a_gap(cases: list[Case], converter: Converter) -> None:
    """The audit can fail. Drop every case for one rule and it must be reported.

    Without this, a bug that made `coverage()` count everything as covered would look
    exactly like a clean data boundary.
    """
    victim = "palat.assim"
    thinned = [c for c in cases if c.rule != victim]
    # The sentence cases would still reach the rule by replay, so blank them too: what
    # is being tested is that a rule with nothing behind it is noticed.
    thinned = [c for c in thinned if c.kind not in {"gold", "heldout", "regression"}]
    report = coverage(DATA_DIR, thinned, converter)
    assert not report.ok
    assert any(gap.kind == "rule" and gap.name == victim for gap in report.gaps)


def test_an_unknown_data_file_opens_a_gap(
    cases: list[Case], converter: Converter, tmp_path: Path
) -> None:
    """A new data file is uncovered until someone says what it is for.

    This is the half that catches drift: files arrive in `data/` over time, and the
    default has to be "not part of the contract yet", not silence.
    """
    report = coverage(DATA_DIR, cases, converter)
    invented = replace(report, data_files={**report.data_files, "lexicon/brand_new.tsv": 0})
    assert not invented.ok
    assert any(gap.name == "lexicon/brand_new.tsv" for gap in invented.gaps)


def test_every_exemption_gives_a_reason() -> None:
    """An exemption is a sentence someone wrote, not a pattern that swallowed a file."""
    for name, reason in {**EXEMPT_DATA, **EXEMPT_RULES}.items():
        assert len(reason) > 30, f"{name}: the exemption reason is too short to be one"


def test_exemptions_do_not_outlive_their_files(cases: list[Case], converter: Converter) -> None:
    """A stale exemption is a hole nobody can see.

    If a file is deleted or a rule renamed, its exemption stops applying to anything and
    silently keeps a future file of the same name out of the audit.
    """
    report = coverage(DATA_DIR, cases, converter)
    stale_data = set(EXEMPT_DATA) - set(report.data_files)
    stale_rules = set(EXEMPT_RULES) - set(report.rules)
    assert not stale_data, f"exempt but no longer shipped: {sorted(stale_data)}"
    assert not stale_rules, f"exempt but no longer a rule: {sorted(stale_rules)}"
