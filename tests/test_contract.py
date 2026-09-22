"""The frozen response contract, as `docs/API.md` states it.

This shape is the same in every implementation of pravapis, so these tests are less
about Python than about the contract: the field names and their order, the fact that
`changes` is never absent, that offsets index the OUTPUT in code points, that the
sanitizer's own edits are never reported as changes, and that `context` appears exactly
when a rule read a neighbouring word.

If one of these fails, read `docs/API.md` first. That document is normative; the code is
what has to move.
"""

from __future__ import annotations

import pytest

from pravapis import convert
from pravapis.pipeline import Converter, parse_options
from pravapis.types import Method, Orthography

RESPONSE_FIELDS = [
    "text",
    "direction",
    "engine_version",
    "data_version",
    "changes",
    "unresolved",
]
CHANGE_FIELDS = ["start", "end", "from", "to", "stage", "rule", "citation", "context"]
N2T = Orthography.TARASKIEVICA
T2N = Orthography.NARKAMAUKA


def test_options_form_returns_text_and_changes() -> None:
    result = convert("снег", {"from": "narkamauka", "to": "taraskievica"})
    assert result.to_dict()["text"] == "сьнег"
    (change,) = result.to_dict()["changes"]
    assert change["from"] == "снег"
    assert change["to"] == "сьнег"


def test_response_has_exactly_the_frozen_fields() -> None:
    payload = convert("снег", {"to": "taraskievica"}).to_dict()
    assert list(payload) == RESPONSE_FIELDS, "the wire shape is frozen; field order included"


def test_change_has_exactly_the_frozen_fields() -> None:
    result = convert("снег", {"to": "taraskievica"})
    (change,) = result.to_dict()["changes"]
    assert list(change) == CHANGE_FIELDS, "the wire shape is frozen; field order included"


def test_direction_names_the_journey_not_the_destination() -> None:
    """`n2t`, not `taraskievica`.

    The target orthography alone does not say where the text started, and without that
    a reader cannot interpret `from` and `to`. Requests name a destination; responses
    name a direction.
    """
    assert convert("снег", {"to": "taraskievica"}).to_dict()["direction"] == "n2t"
    assert convert("сьнег", {"to": "narkamauka"}).to_dict()["direction"] == "t2n"


def test_the_two_versions_are_independent() -> None:
    """Engine and data are separate lines. A response that conflated them would leave a
    bug report ambiguous about which one to bisect."""
    from pravapis import __version__
    from pravapis.dataversion import read_data_version

    payload = convert("снег", {"to": "taraskievica"}).to_dict()
    assert payload["engine_version"] == __version__
    assert payload["data_version"] == read_data_version()
    assert payload["engine_version"] != payload["data_version"]


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
    assert all(c.start >= 0 and c.end > c.start for c in result.conversions)


def test_unchanged_words_are_not_changes(converter: Converter) -> None:
    result = converter.convert("і", N2T)
    assert result.conversions  # the word was seen
    assert result.changes == ()  # and nothing happened to it


# --- offsets ---------------------------------------------------------------------
def test_offsets_index_the_output(converter: Converter) -> None:
    """`start`/`end` slice `text`, the string the caller is holding.

    Input offsets are not recoverable from the output — снег → сьнег is four code points
    becoming five — so indexing the input would give a caller nothing to highlight.
    """
    result = converter.convert("Снег і план сістэмы, свіння", N2T)
    for change in result.changes:
        assert result.text[change.start : change.end] == change.target


def test_offsets_hold_when_sanitize_changes_the_length(converter: Converter) -> None:
    """A zero-width character is stripped before conversion, so the spans index the
    post-sanitize output rather than anything the caller typed."""
    result = converter.convert("​снег план", N2T)
    assert result.changes
    for change in result.changes:
        assert result.text[change.start : change.end] == change.target


def test_offsets_are_code_points_not_utf16_units(converter: Converter) -> None:
    """The decision that costs a JS port a bug if it is left implicit.

    An astral character is one code point and two UTF-16 units. Python slices by the
    former, JavaScript by the latter. They agree on every Cyrillic letter and disagree
    here, which is why the conformance corpus carries `offsets` cases.
    """
    result = converter.convert("🎉 Снег", N2T)
    (change,) = result.changes
    assert change.start == 2, "code points: the emoji is one"
    utf16_index = len(result.text[: change.start].encode("utf-16-le")) // 2
    assert utf16_index == 3, "UTF-16 units: the emoji is two — this is the trap"
    assert result.text[change.start : change.end] == "Сьнег"


def test_offsets_survive_an_astral_character_between_two_changes(
    converter: Converter,
) -> None:
    result = converter.convert("Снег 🎉 план", N2T)
    first, second = result.changes
    assert result.text[first.start : first.end] == first.target
    assert result.text[second.start : second.end] == second.target


# --- the sanitizer is not a change -----------------------------------------------
def test_sanitizer_edits_are_not_reported_as_changes(converter: Converter) -> None:
    """Homoglyphs, apostrophes and zero-width characters are hygiene, not orthography.

    Reporting them would bury the handful of real conversions under one entry per curly
    quote in a pasted paragraph.
    """
    result = converter.convert("​з'ява лaпа", N2T)  # Latin 'a' in лaпа
    assert result.text != "​з'ява лaпа", "the sanitizer did change the text"
    for change in result.changes:
        assert change.source != change.target, "a reported change must be a real change"


def test_a_purely_sanitized_text_reports_no_changes(converter: Converter) -> None:
    """Nothing orthographic happened, so `changes` is empty even though `text` moved."""
    result = converter.convert("лaпa", N2T)  # both vowels are Latin look-alikes
    assert result.text == "лапа"
    assert result.changes == ()


# --- context ---------------------------------------------------------------------
def test_context_is_null_for_a_word_internal_rule(converter: Converter) -> None:
    """`null` is a positive claim: this change is reproducible from the word alone."""
    (change,) = converter.convert("снег", N2T).changes
    assert change.context is None


def test_context_is_set_for_a_cross_word_rule(converter: Converter) -> None:
    changes = {c.source: c for c in converter.convert("Ён не быў", N2T).changes}
    assert changes["не"].context is not None
    assert changes["не"].context.trigger == "next_word"


def test_context_records_what_the_rule_reached_across(converter: Converter) -> None:
    """§18 Заўвага makes a quotation mark transparent, so the rule fires over one."""
    result = converter.convert("сталіца «Украіны»", N2T)
    (change,) = [c for c in result.changes if c.source == "Украіны"]
    assert change.context is not None
    assert change.context.trigger == "prev_word_vowel"
    assert change.context.across == "«"


def test_the_same_rule_is_cross_word_in_one_direction_only(converter: Converter) -> None:
    """§18 forward is conditional on a preceding vowel; Правілы 2008 §15 п.4 backward is
    categorical and reads nothing. Same rule id, different context, both correct."""
    forward = converter.convert("сталіца Украіны", N2T)
    (there,) = [c for c in forward.changes if c.rule_id == "morph.initial_u_w"]
    assert there.context is not None

    back = converter.convert("сталіца Ўкраіны", T2N)
    (returned,) = [c for c in back.changes if c.rule_id == "morph.initial_u_w"]
    assert returned.context is None


# --- unresolved -------------------------------------------------------------------
def test_unresolved_names_the_words_the_converter_declined(converter: Converter) -> None:
    """Not every unchanged word — only the ones that matched an ambiguity trigger and
    that no stage resolved. Silence is right; a silent silence is not."""
    result = converter.convert("без мяне", N2T)
    assert "мяне" in result.unresolved


def test_unresolved_is_empty_when_nothing_was_ambiguous(converter: Converter) -> None:
    assert converter.convert("снег", N2T).unresolved == ()


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
