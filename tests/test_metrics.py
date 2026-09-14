from __future__ import annotations

import pytest

from belnorm.metrics import evaluate, word_accuracy
from belnorm.pipeline import Converter
from belnorm.types import Orthography

N2T = Orthography.TARASKIEVICA


def test_word_accuracy() -> None:
    assert word_accuracy(["a", "b"], ["a", "c"]) == 0.5
    with pytest.raises(ValueError):
        word_accuracy(["a"], [])


def test_baseline_and_change_split(converter: Converter) -> None:
    # 4 words: снег→сьнег and свет→сьвет change; "і" and "дом" do not.
    pairs = [("снег і свет", "сьнег і сьвет"), ("дом", "дом")]
    rep = evaluate(converter, pairs, N2T, round_trip=False)
    assert rep.words == 4
    assert rep.changed_words == 2
    assert rep.unchanged_words == 2
    assert rep.baseline_accuracy == 0.5
    assert rep.baseline_sentence_accuracy == 0.5
    assert rep.change_accuracy == 1.0
    assert rep.false_positive_rate == 0.0
    assert rep.error_reduction == 1.0


def test_false_positive_is_counted(converter: Converter) -> None:
    # Gold (deliberately) says снег stays: the rule firing is a false positive.
    rep = evaluate(converter, [("снег", "снег")], N2T, round_trip=False)
    assert rep.changed_words == 0
    assert rep.false_positives == 1
    assert rep.false_positive_rate == 1.0
    assert rep.baseline_accuracy == 1.0
    assert rep.accuracy == 0.0


def test_missed_change_is_not_a_false_positive(converter: Converter) -> None:
    rep = evaluate(converter, [("дом", "дамок")], N2T, round_trip=False)
    assert rep.changed_words == 1
    assert rep.changed_correct == 0
    assert rep.false_positives == 0
    assert rep.error_reduction == 0.0
