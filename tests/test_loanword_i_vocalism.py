"""Loan і hardening is confined to the explicitly licensed stem span."""

import pytest

from pravapis.pipeline import Converter
from pravapis.rules.engine import RuleEngine
from pravapis.rules.loanwords import apply_i_to_y, i_to_y
from pravapis.types import Orthography

N2T = Orthography.TARASKIEVICA
T2N = Orthography.NARKAMAUKA


@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        ("сістэма", "сыстэма"),
        ("сістэмамі", "сыстэмамі"),
        ("фізіка", "фізыка"),
        ("фізікай", "фізыкай"),
        ("фізічны", "фізычны"),
        ("апазіцыя", "апазыцыя"),
        ("апазіцыі", "апазыцыі"),
        ("сігналізацыя", "сыгналізацыя"),
        ("крытыка", "крытыка"),
    ],
)
def test_whitelisted_loans_roundtrip(
    engine: RuleEngine, converter: Converter, nark: str, tarask: str
) -> None:
    assert engine.apply(nark, N2T)[0] == tarask
    assert engine.apply(tarask, T2N)[0] == nark
    for case in (str.lower, str.title, str.upper):
        assert converter.convert(case(nark), N2T).text == case(tarask)
        assert converter.convert(case(tarask), T2N).text == case(nark)


@pytest.mark.parametrize(
    "word",
    [
        "сіла",
        "сіні",
        "сівая",
        "зіма",
        "зімовы",
        "ціха",
        "цішыня",
        "сядзіце",
        "фініш",
        "лацінскі",
        "сіці",
        "пенсія",
        "марксізм",
    ],
)
def test_i_rule_requires_explicit_stem_license(engine: RuleEngine, word: str) -> None:
    match = engine.stem_match(word, N2T)
    if match is not None:
        assert apply_i_to_y(word, match) == word
    assert "loan.i_to_y" not in engine.apply(word, N2T)[1]


def test_i_scanner_and_stem_boundary(engine: RuleEngine) -> None:
    # The primitive handles all requested pairs; the wrapper supplies etymology.
    assert i_to_y("сізіціфі") == "сызыцыфі"
    match = engine.stem_match("фізікі", N2T)
    assert match is not None
    assert apply_i_to_y("фізікі", match) == "фізыкі"
