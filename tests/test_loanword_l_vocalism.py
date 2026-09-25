"""European loanword stems soften l without rewriting native vocabulary."""

import pytest

from pravapis.pipeline import Converter
from pravapis.rules.engine import RuleEngine
from pravapis.types import Orthography

N2T = Orthography.TARASKIEVICA
T2N = Orthography.NARKAMAUKA


@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        ("план", "плян"),
        ("планамі", "плянамі"),
        ("класіка", "клясыка"),
        ("класікай", "клясыкай"),
        ("логіка", "лёгіка"),
        ("логікай", "лёгікай"),
        ("філасофія", "філязофія"),
        ("філасофіі", "філязофіі"),
        ("філасофскі", "філязофскі"),
        ("клуб", "клюб"),
        ("клубамі", "клюбамі"),
    ],
)
def test_loanword_stems_bidirectional(
    engine: RuleEngine, converter: Converter, nark: str, tarask: str
) -> None:
    # Check the rules separately so whole-word lexicon entries cannot hide gaps.
    assert engine.apply(nark, N2T)[0] == tarask
    assert engine.apply(tarask, T2N)[0] == nark
    for source, target in (
        (nark, tarask),
        (nark.title(), tarask.title()),
        (nark.upper(), tarask.upper()),
    ):
        assert converter.convert(source, N2T).text == target
        assert converter.convert(target, T2N).text == source


@pytest.mark.parametrize("direction", [N2T, T2N])
@pytest.mark.parametrize(
    "word",
    [
        "плаваць",
        "плавалі",
        "лапа",
        "лапамі",
        "лыжка",
        "лыжкамі",
        "лясок",
        "лёд",
        "людзі",
        "клубень",
    ],
)
def test_native_words_unchanged(
    engine: RuleEngine, converter: Converter, word: str, direction: Orthography
) -> None:
    result, fired = engine.apply(word, direction)
    assert result == word
    assert not any(rule.startswith("loan.") for rule in fired)
    assert converter.convert(word, direction).text == word


def test_loanword_token_boundaries(converter: Converter) -> None:
    nark = "«Сцяг», (логіка);\nплаваць, лапа, лыжка — КЛУБ!"
    tarask = "«Сьцяг», (лёгіка);\nплаваць, лапа, лыжка — КЛЮБ!"
    assert converter.convert(nark, N2T).text == tarask
    assert converter.convert(tarask, T2N).text == nark


@pytest.mark.parametrize("ending", ["", "а", "у", "ам", "і", "оў", "амі", "ах"])
def test_native_flag_inflections(engine: RuleEngine, converter: Converter, ending: str) -> None:
    nark, tarask = "сцяг" + ending, "сьцяг" + ending
    for source, target, direction in ((nark, tarask, N2T), (tarask, nark, T2N)):
        result, fired = engine.apply(source, direction)
        assert result == target
        assert not any(rule.startswith("loan.") for rule in fired)
        for case in (str.lower, str.title, str.upper):
            assert converter.convert(case(source), direction).text == case(target)


@pytest.mark.parametrize("direction", [N2T, T2N])
@pytest.mark.parametrize("word", ["флаг", "флагамі", "фляг", "флягамі"])
def test_removed_flag_loan_mapping(
    engine: RuleEngine, converter: Converter, word: str, direction: Orthography
) -> None:
    assert engine.stems[direction].match(word) is None
    assert engine.apply(word, direction)[0] == word
    assert converter.convert(word, direction).text == word
