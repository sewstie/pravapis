"""Transliteration: the transducer, the schemes, and the round trip.

The round trip is the high-value test here, exactly as it is for orthography: it is
checked over every Taraškievica form the project ships — lexicon targets, the gold
set and the mining corpus — rather than over a handful of fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pravapis.metrics import read_gold
from pravapis.normalize import sanitize
from pravapis.pipeline import Converter
from pravapis.tokenize import BELARUSIAN_LETTERS, detokenize, tokenize
from pravapis.translit import (
    PAIRED,
    REVERSIBLE,
    Transliterator,
    scheme_path,
)
from pravapis.translit.engine import (
    CONDITIONS,
    Scheme,
    SchemeError,
    load_scheme,
    transliterate_token,
    validate_scheme,
)
from pravapis.types import Orthography, Script, TokenKind

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

FORWARD = [(Script.LACINKA, False), (Script.OFFICIAL, False), (Script.LACINKA, True)]


@pytest.fixture(scope="session")
def lacinka() -> Transliterator:
    return Transliterator.load(Script.LACINKA, data_dir=DATA)


@pytest.fixture(scope="session")
def lacinka_reverse() -> Transliterator:
    return Transliterator.load(Script.LACINKA, reverse=True, data_dir=DATA)


@pytest.fixture(scope="session")
def official() -> Transliterator:
    return Transliterator.load(Script.OFFICIAL, data_dir=DATA)


def _schemes() -> list[Scheme]:
    return [load_scheme(scheme_path(s, reverse=r, data_dir=DATA)) for s, r in FORWARD]


# --- the schemes' own embedded tests -----------------------------------------------------
@pytest.mark.parametrize("scheme", _schemes(), ids=lambda s: s.name)
def test_embedded_scheme_tests(scheme: Scheme) -> None:
    failures = [
        f"{case.input!r} -> {transliterate_token(scheme, case.input).text!r}, "
        f"expected {case.expected!r}"
        for case in scheme.tests
        if transliterate_token(scheme, case.input).text != case.expected
    ]
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("scheme", _schemes(), ids=lambda s: s.name)
def test_every_scheme_has_tests_and_a_source(scheme: Scheme) -> None:
    assert scheme.tests, f"{scheme.name} has no embedded tests"
    assert scheme.source_label, f"{scheme.name} cites no source"


def test_cyrillic_alphabet_is_fully_covered(
    lacinka: Transliterator, official: Transliterator
) -> None:
    """A scheme with a blind spot would silently pass characters through."""
    alphabet = sorted(BELARUSIAN_LETTERS)
    assert validate_scheme(lacinka.scheme, alphabet) == []
    assert validate_scheme(official.scheme, alphabet) == []


# --- the transducer ----------------------------------------------------------------------
def test_longest_match_wins(lacinka: Transliterator) -> None:
    """дз is consumed whole, so з → z can never re-enter it."""
    assert lacinka.word("дзень").text == "dzień"
    assert lacinka.word("зень").text == "zień"


def test_single_pass_does_not_re_enter_output(lacinka: Transliterator) -> None:
    """A fixpoint engine would turn дж → dž → dž again; this one moves past it."""
    assert lacinka.word("джаз").text == "džaz"


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("яблык", "jabłyk"),  # initial
        ("маяк", "majak"),  # after a vowel
        ("мяса", "miasa"),  # after a consonant
        ("зьява", "źjava"),  # after ь
        ("аб’ява", "abjava"),  # after an apostrophe
        ("маўзэр", "maŭzer"),  # ў counts as a vowel
    ],
)
def test_iotation_contexts(lacinka: Transliterator, word: str, expected: str) -> None:
    assert lacinka.word(word).text == expected


@pytest.mark.parametrize(
    ("word", "expected"),
    [("лес", "les"), ("ляк", "lak"), ("лёд", "lod"), ("любы", "luby"), ("лапа", "łapa")],
)
def test_l_swallows_the_iotation(lacinka: Transliterator, word: str, expected: str) -> None:
    """The one place a consonant absorbs the vowel's i: l already carries softness."""
    assert lacinka.word(word).text == expected


def test_softness_comes_only_from_the_soft_sign(lacinka: Transliterator) -> None:
    """сьвет → śviet (ь), but сядзіба → siadziba (the vowel's own i)."""
    assert lacinka.word("сьвет").text == "śviet"
    assert lacinka.word("сядзіба").text == "siadziba"


def test_case_is_restored_without_shouting(lacinka: Transliterator) -> None:
    assert lacinka.word("Я").text == "Ja"
    assert lacinka.word("Менск").text == "Miensk"
    assert lacinka.word("МЕНСК").text == "MIENSK"


def test_unresolved_characters_are_reported(lacinka: Transliterator) -> None:
    result = lacinka.word("щука")
    assert "щ" in result.unresolved


def test_non_word_tokens_are_untouched(lacinka: Transliterator) -> None:
    text = "Сьнег, 1999 — «сьвет»!\n\tтабуляцыя"
    out = lacinka.transliterate(text).text
    for piece in (", 1999 — «", "»!\n\t"):
        assert piece in out


# --- scheme loading ----------------------------------------------------------------------
def test_unknown_condition_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        'scheme: bad\nmappings:\n  - { from: "а", to: "a", when: on_tuesdays }\n',
        encoding="utf-8",
    )
    with pytest.raises(SchemeError):
        load_scheme(path)


def test_scheme_without_mappings_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("scheme: empty\nmappings: []\n", encoding="utf-8")
    with pytest.raises(SchemeError):
        load_scheme(path)


def test_conditions_are_a_closed_vocabulary() -> None:
    """Scheme files are meant to be checkable against a published table by eye."""
    assert "default" in CONDITIONS
    for scheme in _schemes():
        for mapping in scheme.mappings:
            assert set(mapping.when) <= set(CONDITIONS)


def test_official_has_no_reverse() -> None:
    """It does not write assimilative softness, so reading it back would be a guess."""
    assert Script.OFFICIAL not in REVERSIBLE
    with pytest.raises(SchemeError):
        Transliterator.load(Script.OFFICIAL, reverse=True, data_dir=DATA)


# --- the round trip ----------------------------------------------------------------------
def _taraskievica_corpus(converter: Converter) -> list[str]:
    words: set[str] = set()
    for _, tarask in read_gold(DATA / "eval" / "gold.tsv"):
        words.update(t.text for t in tokenize(tarask) if t.kind is TokenKind.WORD)
    corpus = DATA / "eval" / "roundtrip_corpus.txt"
    if corpus.is_file():
        text = converter.convert(corpus.read_text(encoding="utf-8"), Orthography.TARASKIEVICA).text
        words.update(t.text for t in tokenize(text) if t.kind is TokenKind.WORD)
    return sorted(w for w in words if all(c.lower() in BELARUSIAN_LETTERS for c in w))


#: The one genuine collision in the reverse direction: Cyrillic й + vowel and the
#: iotated vowel both render as j + vowel, so найадметнейшых and наядметнейшых are the
#: same Łacinka string. Documented in data/TRANSLIT.md; not fixable without a separator.
_J_COLLISION = ("йа", "йо", "йу", "йэ", "йі")


def test_lacinka_round_trips_over_the_whole_corpus(
    converter: Converter, lacinka: Transliterator, lacinka_reverse: Transliterator
) -> None:
    """to_cyrillic(to_lacinka(w)) == w for every Taraškievica word the project ships.

    Words the scheme reports as lossy are excluded: a bare ь has no Łacinka rendering,
    so round-tripping it was never on offer. What is *not* excluded is anything else —
    a silent failure here would be a real bug.
    """
    checked = 0
    failures: list[tuple[str, str, str]] = []
    for word in _taraskievica_corpus(converter):
        forward = lacinka.word(word)
        if forward.unresolved:
            continue
        checked += 1
        back = lacinka_reverse.word(forward.text).text
        if back != word:
            failures.append((word, forward.text, back))

    unexpected = [f for f in failures if not any(c in f[0] for c in _J_COLLISION)]
    assert not unexpected, f"unexpected round-trip failures: {unexpected[:10]}"
    assert checked > 3000, f"corpus too small to mean anything: {checked} words"
    rate = 1 - len(failures) / checked
    assert rate >= 0.999, f"round trip {rate:.4%} over {checked} words: {failures[:10]}"


def test_the_j_collision_is_real_and_bounded(
    lacinka: Transliterator, lacinka_reverse: Transliterator
) -> None:
    """Pin the known limitation so it cannot silently widen."""
    assert lacinka.word("найадметнейшых").text == lacinka.word("наядметнейшых").text
    assert lacinka_reverse.word("najadmietniejšych").text == "наядметнейшых"


def test_a_bare_soft_sign_is_reported_not_hidden(lacinka: Transliterator) -> None:
    """ть is not a Belarusian sequence; the ь is dropped and the caller is told."""
    result = lacinka.word("зацірать")
    assert result.text == "zacirat"
    assert result.unresolved == ("ь",)


def test_round_trip_through_the_converter(converter: Converter) -> None:
    """The full loop: Narkamaŭka → Taraškievica → Łacinka → Taraškievica → Narkamaŭka."""
    text = "Снег і свет у Еўропе, план сістэмы."
    latin = converter.render(text, Script.LACINKA)
    assert latin == "Śnieh i śviet u Eŭropie, plan systemy."
    assert converter.read_script(latin, Script.LACINKA, Orthography.NARKAMAUKA) == text


@given(st.text(alphabet=sorted(BELARUSIAN_LETTERS), min_size=1, max_size=24))
def test_transliteration_never_loses_a_token_boundary(word: str) -> None:
    """Whatever the scheme does inside a word, the text's shape survives."""
    lac = Transliterator.load(Script.LACINKA, data_dir=DATA)
    text = f"{word} {word}, {word}."
    out = lac.transliterate(sanitize(text)).text
    assert out.count(" ") == text.count(" ")
    assert out.endswith(".")


@given(st.text(alphabet=[*sorted(BELARUSIAN_LETTERS), " ", ",", "\n"], min_size=0, max_size=40))
def test_tokenize_is_still_lossless_on_latin_output(text: str) -> None:
    lac = Transliterator.load(Script.LACINKA, data_dir=DATA)
    latin = lac.transliterate(sanitize(text)).text
    assert detokenize(tokenize(latin)) == latin


# --- pairing -----------------------------------------------------------------------------
def test_pairing_is_what_makes_the_output_idiomatic(converter: Converter) -> None:
    """Łacinka gets śnieh because it is paired with Taraškievica; --no-convert gets snieh."""
    assert converter.render("снег", Script.LACINKA) == "śnieh"
    assert converter.render("снег", Script.LACINKA, convert=False) == "snieh"
    assert converter.render("снег", Script.OFFICIAL) == "snieh"


def test_every_latin_script_is_paired() -> None:
    for script in Script:
        if script.is_latin:
            assert script in PAIRED


def test_sanitize_folds_towards_the_script() -> None:
    """A Łacinka text typed on a Belarusian layout picks up Cyrillic look-alikes."""
    assert sanitize("cнег") == "снег"  # Latin c inside a Cyrillic run
    assert sanitize("śniеh", Script.LACINKA) == "śnieh"  # Cyrillic е inside a Latin run


@pytest.mark.parametrize("script", [Script.CYRILLIC, Script.LACINKA, Script.OFFICIAL])
def test_sanitize_is_idempotent_per_script(script: Script) -> None:
    for text in ("сьнег", "śnieh", "Eŭropa", "аб’ява"):
        once = sanitize(text, script)
        assert sanitize(once, script) == once
