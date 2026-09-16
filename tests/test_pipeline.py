from __future__ import annotations

import pytest

from pravapis import convert as module_convert
from pravapis.lexicon.store import Lexicon
from pravapis.pipeline import Converter
from pravapis.rules.engine import RuleEngine
from pravapis.tokenize import tokenize
from pravapis.types import Method, Orthography

N2T = Orthography.TARASKIEVICA
T2N = Orthography.NARKAMAUKA

SENTENCES: list[tuple[str, str]] = [
    ("Учора ішоў снег.", "Учора ішоў сьнег."),
    # мяне+ is end-stressed: no jakanne (§3), but §29 softness before soft м: безь.
    ("Без мяне не пачынайце.", "Безь мяне не пачынайце."),
    ("З’ява была нечаканай.", "Зьява была нечаканай."),
    ("Мы жывём у Мінску.", "Мы жывём у Менску."),
    ("Свіння спіць.", "Сьвіньня сьпіць."),
    ("Суддзя вынес рашэнне.", "Судзьдзя вынес рашэньне."),
    ("Тэатр адкрыўся зноў.", "Тэатар адкрыўся зноў."),
    ("Ён не ведае адказу.", "Ён ня ведае адказу."),
    ("З ім было весела.", "Зь ім было весела."),
    ("Пісьменнік напісаў кнігу.", "Пісьменьнік напісаў кнігу."),
    ("Класічная МУЗЫКА", "Клясычная МУЗЫКА"),
    ("Еўропа і Азія", "Эўропа і Азія"),
    ("не, быў", "не, быў"),  # punctuation breaks the clitic
]


@pytest.mark.parametrize(("nark", "tarask"), SENTENCES)
def test_sentences_n2t(converter: Converter, nark: str, tarask: str) -> None:
    assert converter.convert(nark, N2T).text == tarask


@pytest.mark.parametrize(("nark", "tarask"), SENTENCES)
def test_sentences_round_trip(converter: Converter, nark: str, tarask: str) -> None:
    assert converter.convert(tarask, T2N).text == nark


def test_methods_and_stats(converter: Converter) -> None:
    result = converter.convert("Лапа, снег, Мінск, привет, xyz", N2T)
    by_source = {c.source: c for c in result.conversions}
    assert by_source["Лапа"].method is Method.IDENTITY
    assert by_source["снег"].method is Method.RULE
    assert by_source["снег"].rule_id == "palat.assim"
    assert by_source["Мінск"].method is Method.LEXICON
    assert by_source["привет"].method is Method.UNKNOWN  # Russian: passed through
    assert "xyz" not in by_source  # Latin is not a word token
    assert result.stats[Method.IDENTITY] == 1
    assert result.stats[Method.RULE] == 1
    assert result.stats[Method.LEXICON] == 1
    assert result.stats[Method.UNKNOWN] == 1
    assert sum(result.stats.values()) == len(result.conversions) == 4


def test_layout_preserved(converter: Converter) -> None:
    text = "  Снег!\n\tсвет...  \n"
    assert converter.convert(text, N2T).text == "  Сьнег!\n\tсьвет...  \n"


def test_input_is_sanitized_once(converter: Converter) -> None:
    # Latin homoglyph c, ASCII apostrophe, zero-width space
    assert converter.convert("cнег з'ява сь​нег", N2T).text == "сьнег зьява сьнег"


def test_hyphenated_compound(converter: Converter) -> None:
    conv = converter.convert_word("снег-Мінск", N2T)
    assert conv.target == "сьнег-Менск"
    assert conv.method is Method.RULE  # strongest changed part
    assert conv.rule_id == "palat.assim"
    assert converter.convert_word("лапа-лапа", N2T).method is Method.IDENTITY
    assert converter.convert_word("так-сяк", N2T).method is Method.UNKNOWN


def test_convert_word_uses_right_context(converter: Converter) -> None:
    tokens = tokenize("не быў")
    conv = converter.convert_word("не", N2T, tokens[1:])
    assert conv.target == "ня"
    assert conv.method is Method.RULE
    assert conv.rule_id == "morph.particle"
    assert converter.convert_word("не", N2T).target == "не"


def test_explain_traces(converter: Converter) -> None:
    (e,) = converter.explain("свіння", N2T)
    assert e.target == "сьвіньня"
    assert [t.rule_id for t in e.traces] == ["palat.geminate", "palat.assim"]
    assert e.traces[0].before == "свіння"
    assert e.traces[-1].after == "сьвіньня"
    (p,) = [x for x in converter.explain("не быў", N2T) if x.source == "не"]
    assert p.traces[0].rule_id == "morph.particle"


def test_case_patterns(converter: Converter) -> None:
    assert converter.convert("СНЕГ Снег снег", N2T).text == "СЬНЕГ Сьнег сьнег"
    assert converter.convert("У Мінску", N2T).text == "У Менску"


def test_identity_beats_rules(engine: RuleEngine) -> None:
    lex = Lexicon.from_pairs([("снег", "снег")])
    conv = Converter(lex, engine).convert_word("снег", N2T)
    assert conv.method is Method.IDENTITY
    assert conv.target == "снег"


def test_lexicon_beats_rules(converter: Converter) -> None:
    # "метр" would become "метар" by rule; the lexicon says "мэтар".
    conv = converter.convert_word("метр", N2T)
    assert conv.method is Method.LEXICON
    assert conv.target == "мэтар"


def test_unknown_passthrough_has_no_rule(converter: Converter) -> None:
    conv = converter.convert_word("дом", N2T)
    assert conv.method is Method.UNKNOWN
    assert conv.rule_id is None
    assert conv.target == "дом"


def test_empty_and_non_word_input(converter: Converter) -> None:
    result = converter.convert("", N2T)
    assert result.text == ""
    assert result.conversions == ()
    assert converter.convert("123 ... !!!", N2T).text == "123 ... !!!"


def test_module_level_convert() -> None:
    assert module_convert("снег", N2T) == "сьнег"
    assert module_convert("сьнег", T2N) == "снег"


def test_is_ambiguous_triggers(converter: Converter) -> None:
    assert converter.is_ambiguous("не")
    assert converter.is_ambiguous("план")
    assert converter.is_ambiguous("сістэма")
    assert not converter.is_ambiguous("дом")
