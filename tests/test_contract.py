"""The frozen public signature: convert(text, {from, to}) → {text, changes}.

This shape is the same in every implementation of pravapis, so these tests are less
about Python than about the contract: the field names, the fact that `changes` is never
absent, and the fact that `explain` is a view over the same decisions rather than a
second opinion.
"""

from __future__ import annotations

import pytest

from pravapis import convert
from pravapis.normalize import sanitize
from pravapis.pipeline import Converter, parse_options
from pravapis.types import Method, Orthography

CHANGE_FIELDS = ["from", "to", "offset", "rule", "class", "citation"]
N2T = Orthography.TARASKIEVICA


def test_options_form_returns_text_and_changes() -> None:
    result = convert("снег", {"from": "narkamauka", "to": "taraskievica"})
    assert result.to_dict()["text"] == "сьнег"
    (change,) = result.to_dict()["changes"]
    assert change["from"] == "снег"
    assert change["to"] == "сьнег"


def test_change_has_exactly_the_frozen_fields() -> None:
    result = convert("снег", {"to": "taraskievica"})
    (change,) = result.to_dict()["changes"]
    assert list(change) == CHANGE_FIELDS, "the wire shape is frozen; field order included"


def test_from_may_be_omitted() -> None:
    """There are two orthographies, so `to` alone is unambiguous."""
    assert convert("снег", {"to": "taraskievica"}).text == "сьнег"


def test_from_must_be_the_other_one() -> None:
    with pytest.raises(ValueError, match="nothing to convert"):
        parse_options({"from": "taraskievica", "to": "taraskievica"})


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({}, "needs a 'to'"),
        ({"from": "narkamauka"}, "needs a 'to'"),
        ({"to": "klingon"}, "unknown orthography"),
        ({"from": "klingon", "to": "taraskievica"}, "unknown orthography"),
        ({"to": "taraskievica", "mode": "loud"}, "unknown option"),
    ],
)
def test_bad_options_are_rejected(options: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_options(options)


def test_legacy_orthography_form_still_returns_a_string() -> None:
    assert convert("снег", Orthography.TARASKIEVICA) == "сьнег"


# --- changes are always there ----------------------------------------------------
def test_changes_are_not_behind_a_flag(converter: Converter) -> None:
    result = converter.convert("Снег і план сістэмы", N2T)
    assert [c.source for c in result.changes] == ["Снег", "план", "сістэмы"]
    assert all(c.offset >= 0 for c in result.conversions)


def test_unchanged_words_are_not_changes(converter: Converter) -> None:
    result = converter.convert("і", N2T)
    assert result.conversions  # the word was seen
    assert result.changes == ()  # and nothing happened to it


def test_offsets_index_the_sanitized_input(converter: Converter) -> None:
    text = "Снег і план сістэмы, свіння"
    clean = sanitize(text)
    for change in converter.convert(text, N2T).changes:
        assert clean[change.offset : change.offset + len(change.source)] == change.source


def test_offsets_hold_when_sanitize_changes_the_length(converter: Converter) -> None:
    """A zero-width character is stripped, so offsets must index the cleaned string."""
    text = "​снег план"
    clean = sanitize(text)
    assert len(clean) < len(text)
    for change in converter.convert(text, N2T).changes:
        assert clean[change.offset : change.offset + len(change.source)] == change.source


# --- citations -------------------------------------------------------------------
def test_rule_changes_carry_their_citation(converter: Converter) -> None:
    (change,) = converter.convert("снег", N2T).changes
    assert change.rule_id == "palat.assim"
    assert change.citation == "Збор 2005, §29"


def test_composed_rules_compose_their_citations(converter: Converter) -> None:
    (change,) = converter.convert("свіння", N2T).changes
    assert "+" in str(change.rule_id)
    assert change.citation is not None
    assert change.citation.count("Збор 2005") >= 2


def test_lexicon_hits_say_nothing_they_cannot_back(converter: Converter) -> None:
    """A lexicon entry is its own evidence; inventing a § for it would be a guess."""
    (change,) = converter.convert("план", N2T).changes
    assert change.method is Method.LEXICON
    assert change.citation is None


# --- explain is a view -----------------------------------------------------------
def test_explain_agrees_with_convert(converter: Converter) -> None:
    text = "Снег і план сістэмы, свіння і без мяне"
    result = converter.convert(text, N2T)
    explanations = converter.explain(text, N2T)
    assert len(explanations) == len(result.conversions)
    for explanation, conversion in zip(explanations, result.conversions, strict=True):
        assert explanation.source == conversion.source
        assert explanation.target == conversion.target
        assert explanation.method is conversion.method
        assert explanation.rule_id == conversion.rule_id


def test_explain_adds_traces_and_nothing_else(converter: Converter) -> None:
    (explanation,) = converter.explain("свіння", N2T)
    assert [t.rule_id for t in explanation.traces] == ["palat.geminate", "palat.assim"]
    assert explanation.target == "сьвіньня"


def test_explain_still_explains_the_clitic_rules(converter: Converter) -> None:
    explanations = converter.explain("без мяне", N2T)
    first = explanations[0]
    assert first.target == "безь"
    assert any("particle" in t.rule_id for t in first.traces)
