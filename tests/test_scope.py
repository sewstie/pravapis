"""The contract boundary: what counts as a change the converter owes.

These tests are the guard on the headline number. If the fold quietly grows a rule, or
a bucket quietly widens, recall moves without anything in the converter changing — and
that is the failure mode that makes an evaluation harness worse than none.
"""

from __future__ import annotations

import pytest

from pravapis.scope import (
    Scope,
    classify_scope,
    fold_similarity,
    format_interval,
    neutral_fold,
    wilson,
)


@pytest.mark.parametrize(
    ("narkamauka", "taraskievica"),
    [
        ("снег", "сьнег"),  # assimilative softness
        ("сезон", "сэзон"),  # loan э
        ("сістэма", "сыстэма"),  # loan ы and э
        ("план", "плян"),  # soft л
        ("Еўропа", "Эўропа"),  # еў → эў
        ("блок", "блёк"),  # soft л with ё
        ("гуль", "гуль"),  # unchanged
    ],
)
def test_modelled_alternations_fold_together(narkamauka: str, taraskievica: str) -> None:
    assert neutral_fold(narkamauka) == neutral_fold(taraskievica)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("плошча", "пляц"),  # different words
        ("горад", "места"),  # different words
        ("завода", "заводу"),  # a case ending, not a spelling
    ],
)
def test_different_words_do_not_fold_together(a: str, b: str) -> None:
    assert neutral_fold(a) != neutral_fold(b)


def test_the_fold_is_idempotent() -> None:
    for word in ("сьнег", "сыстэма", "плян", "Эўропа"):
        assert neutral_fold(neutral_fold(word)) == neutral_fold(word)


def test_folding_removes_the_similarity_penalty_for_orthography() -> None:
    """The bias the fold exists to remove: a heavily converted sentence must not look
    less similar to its counterpart than a barely converted one."""
    from difflib import SequenceMatcher

    dense_n, dense_t = "сістэма прафілактыкі сезону", "сыстэма прафіляктыкі сэзону"
    raw = SequenceMatcher(None, dense_n, dense_t, autojunk=False).ratio()
    assert raw < 0.95  # raw similarity punishes it
    assert fold_similarity(dense_n, dense_t) == 1.0  # folded, it is free


# --- buckets --------------------------------------------------------------------------
def test_an_orthographic_difference_is_in_scope() -> None:
    scope, _ = classify_scope("снег", "сьнег")
    assert scope is Scope.IN_SCOPE


def test_a_case_ending_is_grammatical_and_says_why() -> None:
    scope, reason = classify_scope("завода", "заводу")
    assert scope is Scope.GRAMMATICAL
    assert "spelling code" in reason


def test_a_genitive_plural_is_grammatical() -> None:
    scope, _ = classify_scope("хвілін", "хвілінаў")
    assert scope is Scope.GRAMMATICAL


def test_a_different_word_is_not_orthographic() -> None:
    scope, _ = classify_scope("плошчы", "пляцы")
    assert scope is Scope.NOT_ORTHOGRAPHIC


def test_in_scope_wins_over_an_exclusion_that_would_also_match() -> None:
    """A pair that differs only by modelled alternations must never be excluded."""
    # folds identical, and also looks like an -а/-у ending change on the raw strings
    scope, _ = classify_scope("сезона", "сэзона")
    assert scope is Scope.IN_SCOPE


def test_every_bucket_carries_a_reason() -> None:
    for a, b in [("снег", "сьнег"), ("завода", "заводу"), ("плошчы", "пляцы")]:
        _, reason = classify_scope(a, b)
        assert reason and len(reason) > 10


# --- intervals --------------------------------------------------------------------------
def test_wilson_brackets_the_point_estimate() -> None:
    low, high = wilson(30, 100)
    assert low < 0.30 < high


def test_wilson_stays_inside_zero_and_one_at_the_extremes() -> None:
    """The normal approximation runs past the ends here; Wilson is why we use it."""
    low, high = wilson(0, 20)
    assert low == 0.0 and 0.0 < high < 0.25
    low, high = wilson(20, 20)
    assert 0.75 < low < 1.0 and high == 1.0


def test_a_smaller_sample_gives_a_wider_interval() -> None:
    narrow = wilson(300, 1000)
    wide = wilson(30, 100)
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])


def test_format_interval_shows_the_number_and_its_worth() -> None:
    assert format_interval(30, 100).startswith("30.0% [")
    assert format_interval(0, 0) == "—"
