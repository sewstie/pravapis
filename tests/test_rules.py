from __future__ import annotations

import pytest

from pravapis.lexicon.stems import StemMatch, WordClass
from pravapis.rules import loanwords, morphology
from pravapis.rules.engine import Rule, RuleEngine, RuleError, RuleTest, validate_rule_set
from pravapis.rules.palatalization import (
    is_palatalizing_context,
    mark_assimilative_softness,
    unmark_assimilative_softness,
)
from pravapis.stress import StressTable
from pravapis.types import Orthography

N2T = Orthography.TARASKIEVICA
T2N = Orthography.NARKAMAUKA

# --- table-driven: assimilative softness ---------------------------------------------
PALATALIZATION_PAIRS: list[tuple[str, str]] = [
    ("снег", "сьнег"),
    ("свет", "сьвет"),
    ("песня", "песьня"),
    ("дзверы", "дзьверы"),
    ("свіння", "сьвіньня"),
    ("сцвярджаць", "сьцьвярджаць"),
    ("косць", "косьць"),
    ("здзейсніць", "зьдзейсьніць"),
    ("насенне", "насеньне"),
    ("жыццё", "жыцьцё"),
    ("вяселле", "вясельле"),
    ("суддзя", "судзьдзя"),
    ("з’ява", "зьява"),
    ("з’езд", "зьезд"),
    ("рассцілаць", "расьсьцілаць"),
    ("развіццё", "разьвіцьцё"),
    ("змена", "зьмена"),
    ("спяваць", "сьпяваць"),
    ("цвік", "цьвік"),
    ("збіраць", "зьбіраць"),
    ("пасля", "пасьля"),
    # unchanged
    ("падсекчы", "падсекчы"),
    ("адзначыць", "адзначыць"),
    ("скептык", "скептык"),
    ("склеп", "склеп"),
    ("пісьмо", "пісьмо"),
    ("касьба", "касьба"),
    ("аб’ява", "аб’ява"),
    ("гусь", "гусь"),
    ("ванна", "ванна"),
]


@pytest.mark.parametrize(("nark", "tarask"), PALATALIZATION_PAIRS)
def test_mark_softness(nark: str, tarask: str) -> None:
    assert mark_assimilative_softness(nark) == tarask


@pytest.mark.parametrize(("nark", "tarask"), PALATALIZATION_PAIRS)
def test_unmark_softness(nark: str, tarask: str) -> None:
    assert unmark_assimilative_softness(tarask) == nark


@pytest.mark.parametrize(("nark", "tarask"), PALATALIZATION_PAIRS)
def test_yaml_rules_agree_with_reference_functions(
    engine: RuleEngine, nark: str, tarask: str
) -> None:
    assert engine.apply(nark, N2T)[0] == tarask
    assert engine.apply(tarask, T2N)[0] == nark


def test_is_palatalizing_context() -> None:
    assert is_palatalizing_context("снег", 0)
    assert is_palatalizing_context("дзверы", 0)
    assert is_palatalizing_context("свіння", 3)  # н before н+я
    assert not is_palatalizing_context("свіння", 4)
    assert not is_palatalizing_context("скептык", 0)
    assert not is_palatalizing_context("снег", 1)
    assert not is_palatalizing_context("снег", 99)


# --- YAML-embedded rule tests ---------------------------------------------------------
def _rule_cases(engine: RuleEngine) -> list[tuple[Rule, RuleTest]]:
    return [(rule, case) for rule in engine.rules for case in rule.tests]


def test_every_rule_has_tests(engine: RuleEngine) -> None:
    untested = [r.id for r in engine.rules if not r.tests]
    assert not untested, f"rules without embedded tests: {untested}"


def test_embedded_rule_tests(engine: RuleEngine) -> None:
    failures: list[str] = []
    for rule, case in _rule_cases(engine):
        got = rule.transform(case.input, engine.stem_match(case.input, rule.direction))
        if got != case.expected:
            kind = "positive" if case.positive else "negative"
            failures.append(
                f"{rule.id} [{kind}] {case.input!r} -> {got!r}, expected {case.expected!r}"
            )
        if case.positive and case.expected == case.input:
            failures.append(f"{rule.id}: positive case {case.input!r} expects no change")
    assert not failures, "\n".join(failures)


# --- loanwords -------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("план", "плян"),
        ("лампа", "лямпа"),
        ("біялогія", "біялёгія"),
        ("логіка", "лёгіка"),
        ("балкон", "балькон"),
        ("лапа", "лапа"),
        ("падлогі", "падлогі"),
        ("клас", "кляс"),
    ],
)
def test_l_palatalization(word: str, expected: str, engine: RuleEngine) -> None:
    match = engine.stem_match(word, N2T)
    assert match is not None, f"{word!r} is in no stems.tsv entry"
    assert loanwords.apply_l_palatalization(word, match) == expected


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("сістэма", "сыстэма"),
        ("прэзідэнт", "прэзыдэнт"),
        ("апазіцыя", "апазыцыя"),
        ("фізіка", "фізыка"),
        ("сіла", "сіла"),
        ("сіні", "сіні"),
    ],
)
def test_i_to_y(word: str, expected: str, engine: RuleEngine) -> None:
    match = engine.stem_match(word, N2T)
    assert match is not None, f"{word!r} is in no stems.tsv entry"
    assert loanwords.apply_i_to_y(word, match) == expected


def test_eu_prefix() -> None:
    assert loanwords.apply_eu_prefix("еўропа") == "эўропа"
    assert loanwords.apply_eu_prefix("леў") == "леў"


def test_f_substitution() -> None:
    assert loanwords.apply_f_substitution("фёдар") == "хведар"
    assert loanwords.apply_f_substitution("фёдаравіч") == "хведаравіч"
    assert loanwords.apply_f_substitution("фабрыка") == "фабрыка"


def test_g_distinction_roundtrip() -> None:
    """ґ is UNVERIFIED, so its stems are provenance `uncertain` and never reach the
    engine. The transducer itself must still round-trip when handed a match."""
    for word in ("ганак", "гузік", "грунт", "гвалт"):
        match = StemMatch(word, WordClass.LOAN, frozenset({"g"}), 0, len(word))
        g = loanwords.apply_g_distinction(word, match)
        assert g.startswith("ґ")
        assert loanwords.remove_g_distinction(g) == word


def test_uncertain_stems_never_fire(engine: RuleEngine) -> None:
    """Provenance `uncertain` rows are parsed but not applied: ганак stays ганак."""
    assert engine.stem_match("ганак", N2T) is None
    assert engine.apply("ганак", N2T)[0] == "ганак"


# --- morphology / particles --------------------------------------------------------------
@pytest.mark.parametrize(
    ("word", "nxt", "expected"),
    [
        ("не", "быў", "ня"),  # бы+ў
        ("не", "ведае", "ня"),  # ве+дае
        ("не", "працуе", None),
        ("не", "у", None),
        ("не", None, None),
        ("без", "сну", "бяз"),
        ("без", "ліку", "бязь"),  # лі+ку: jakanne, then soft onset
        ("без", "мяне", "безь"),  # мяне+: no jakanne, but §29 softness
        ("без", "якога", "безь"),  # яко+га
        ("без", "людзей", "безь"),  # людзе+й
        ("без", "іголкі", None),  # §29 Заўвага А: unstressed initial і
        ("з", "іх", "зь"),  # і+х: stressed initial і
        ("без", "працы", "бяз"),  # пра+цы; the old word list did not know it
        ("не", "было", None),  # было+ (the old word list had it first-stressed)
        ("не", "мае", None),  # homograph ма+е / мае+: left alone
        ("з", "ім", "зь"),
        ("з", "мяне", "зь"),
        ("з", "табой", None),
        ("праз", "лес", "празь"),
        ("снег", "быў", None),
    ],
)
def test_convert_particle_n2t(
    stress: StressTable, word: str, nxt: str | None, expected: str | None
) -> None:
    assert morphology.convert_particle(word, nxt, N2T, stress) == expected


def test_convert_particle_t2n() -> None:
    assert morphology.convert_particle("ня", "быў", T2N) == "не"
    assert morphology.convert_particle("бязь", "мяне", T2N) == "без"
    assert morphology.convert_particle("зь", "ім", T2N) == "з"
    assert morphology.convert_particle("няма", None, T2N) is None


def test_first_syllable_stress_from_grammardb(stress: StressTable) -> None:
    assert morphology.is_first_syllable_stressed("ведае", stress)
    assert morphology.is_first_syllable_stressed("Толькі", stress)
    assert morphology.is_first_syllable_stressed("бізнес-кантакту", stress)  # first part decides
    assert not morphology.is_first_syllable_stressed("працуе", stress)
    assert not morphology.is_first_syllable_stressed("мяне", stress)
    assert not morphology.is_first_syllable_stressed("у", stress)


def test_first_syllable_stress_without_table() -> None:
    assert morphology.is_first_syllable_stressed("быў")  # monosyllable
    assert morphology.is_first_syllable_stressed("ёлка")  # ё is always stressed
    assert not morphology.is_first_syllable_stressed("ведае")  # unknown without a table
    assert not morphology.is_first_syllable_stressed("у")


# --- engine mechanics --------------------------------------------------------------------
def _rule(rule_id: str, pattern: str, repl: str, **kw: object) -> Rule:
    import regex

    return Rule(id=rule_id, pattern=regex.compile(pattern), replacement=repl, direction=N2T, **kw)  # type: ignore[arg-type]


def test_validate_detects_cycles_and_dangling() -> None:
    a = _rule("a", "x", "y", requires=("b",))
    b = _rule("b", "x", "y", requires=("a",))
    problems = validate_rule_set([a, b])
    assert any("cycle" in p for p in problems)
    assert validate_rule_set([_rule("c", "x", "y", requires=("nope",))])
    assert validate_rule_set([_rule("d", "x", "y"), _rule("d", "x", "z")])
    with pytest.raises(RuleError):
        RuleEngine([a, b])


def test_requires_gates_firing() -> None:
    first = _rule("first", "^а", "б", priority=10)
    second = _rule("second", "б$", "в", requires=("first",))
    engine = RuleEngine([first, second])
    assert engine.apply("аб", N2T) == ("бв", ["first", "second"])
    assert engine.apply("хб", N2T) == ("хб", [])  # `second` needs `first` to fire


def test_priority_order_and_explain() -> None:
    low = _rule("low", "а", "о", priority=1)
    high = _rule("high", "а", "у", priority=5)
    engine = RuleEngine([low, high])
    traces = engine.explain("а", N2T)
    assert [t.rule_id for t in traces] == ["high"]
    assert traces[0].after == "у"


def test_exceptions_skip_rule() -> None:
    rule = _rule("r", "а", "о", exceptions=frozenset({"так"}))
    engine = RuleEngine([rule])
    assert engine.apply("так", N2T) == ("так", [])
    assert engine.apply("там", N2T) == ("том", ["r"])


def test_loaded_engine_shape(engine: RuleEngine) -> None:
    assert len(engine) >= 15
    assert engine.rules_for(N2T)
    assert engine.rules_for(T2N)
    assert engine.get("palat.assim") is not None
    assert engine.get("nope") is None
