"""Regressions pinned to Беларускі клясычны правапіс: Збор правілаў (2005).

Each case either quotes the book or applies a rule it states; the section is in the comment.
"""

from __future__ import annotations

import pytest

from pravapis.pipeline import Converter
from pravapis.rules import loanwords
from pravapis.types import Orthography

N2T = Orthography.TARASKIEVICA
T2N = Orthography.NARKAMAUKA


def _both_ways(converter: Converter, nark: str, tarask: str, *, aggressive: bool = False) -> None:
    assert converter.convert(nark, N2T, aggressive=aggressive).text == tarask
    assert converter.convert(tarask, T2N, aggressive=aggressive).text == nark


# --- §30: ц, дз soften only before в ---------------------------------------------------------
@pytest.mark.parametrize(
    "word",
    [
        "мацнець",  # §30 Заўвага А
        "пэндзлік",  # §30 Заўвага А
        "Цнянка",  # §30 Заўвага А
    ],
)
def test_ts_dz_stay_hard_before_consonants_other_than_v(converter: Converter, word: str) -> None:
    _both_ways(converter, word, word)


@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        ("цвёрды", "цьвёрды"),  # §30
        ("цвік", "цьвік"),  # §30
        ("дзве", "дзьве"),  # §30
        ("дзверы", "дзьверы"),  # §30
        ("сцвярджаць", "сьцьвярджаць"),  # §30 сьцьвердзіць: ц before в, then с before ць (§29)
    ],
)
def test_ts_dz_soften_before_v(converter: Converter, nark: str, tarask: str) -> None:
    _both_ways(converter, nark, tarask)


def test_etymological_dz_soft_sign_survives_reverse(converter: Converter) -> None:
    # §29 Заўвага Б: дзьме has a lexical ь, not an assimilative one
    assert converter.convert("дзьме", T2N).text == "дзьме"


# --- §32, §41 Заўвага А: no soft geminate дз at a prefix boundary ------------------------------
@pytest.mark.parametrize("word", ["аддзел", "аддзячыць", "паддзець"])
def test_prefix_d_before_dz_unchanged(converter: Converter, word: str) -> None:
    _both_ways(converter, word, word)


@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        ("суддзя", "судзьдзя"),  # §40
        ("стагоддзе", "стагодзьдзе"),  # §40
        (
            "Наддзвінне",
            "Наддзьвіньне",
        ),  # §41 Заўвага А: prefix unchanged, root дзьв (§30), ньн (§40)
    ],
)
def test_root_dz_geminate_still_softens(converter: Converter, nark: str, tarask: str) -> None:
    _both_ways(converter, nark, tarask)


# --- §26 Заўвага А: non-traditional proper names keep -тр ---------------------------------------
@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        ("Сартр", "Сартр"),
        ("Нотр-Дам", "Нотр-Дам"),
        ("тэатр", "тэатар"),  # §26
        ("цэнтр", "цэнтар"),  # §26
    ],
)
def test_final_tr(converter: Converter, nark: str, tarask: str) -> None:
    assert converter.convert(nark, N2T).text == tarask


# --- policy: optional forms are left alone unless aggressive -----------------------------------
def test_fyodar_is_valid_and_left_alone(converter: Converter) -> None:
    # §81 Заўвага Б: Тодар, Фёдар, Хведар, Ходар are all valid
    for text in ("Фёдар прыехаў.", "Фёдара няма.", "Фядос"):
        assert converter.convert(text, N2T).text == text


def test_fyodar_becomes_khviedar_only_when_aggressive(converter: Converter) -> None:
    assert converter.convert("Фёдара і Фядоса", N2T, aggressive=True).text == "Хведара й Хвядоса"


def test_filip_not_rewritten_in_any_mode(converter: Converter) -> None:
    # Філіп → Піліп is not in the book: removed, not made optional
    for aggressive in (False, True):
        assert converter.convert("Філіп", N2T, aggressive=aggressive).text == "Філіп"
    assert loanwords.apply_f_substitution("філіп") == "філіп"


@pytest.mark.parametrize(
    ("text", "aggressive_out"),
    [
        ("Сала і цыбуля", "Сала й цыбуля"),  # §13: after a vowel
        ("Мама і тата. І тут.", "Мама й тата. І тут."),  # sentence-initial І unchanged
        ("нарэжце, і пасаліце", "нарэжце, і пасаліце"),  # after punctuation: і
        ("дуб і клён", "дуб і клён"),  # after a consonant: і
        ("яна ідзе", "яна ідзе"),  # word-initial і- never changes (§13)
    ],
)
def test_conjunction_i_to_j_is_optional(
    converter: Converter, text: str, aggressive_out: str
) -> None:
    assert converter.convert(text, N2T).text == text
    assert converter.convert(text, N2T, aggressive=True).text == aggressive_out


def test_aggressive_explain_names_the_rule(converter: Converter) -> None:
    ex = converter.explain("Сала і цыбуля", N2T, aggressive=True)
    assert [(e.source, e.target, e.rule_id) for e in ex][1] == ("і", "й", "morph.conj_i_j")


def test_default_converter_is_not_aggressive(converter: Converter) -> None:
    assert converter.aggressive is False
    assert converter.variant(True).aggressive is True
    assert converter.variant(True).variant(False) is converter


# --- lexicon: personal names ------------------------------------------------------------------
@pytest.mark.parametrize(
    "name",
    [
        "Леанід",  # §48 "Але: Леанід"
        "Павел",  # §55.1 Заўвага А: Павал, Павел both valid
        "Кірыл",  # not in the book
        "Афанасій",  # not in the book
        "Іосіф",  # not in the book
        "Фама",  # not in the book
    ],
)
def test_names_left_unchanged(converter: Converter, name: str) -> None:
    assert converter.convert(name, N2T).text == name


@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        ("Дзмітрый", "Дзьмітры"),  # §17 base form, not the optional Зьміцер
        ("Валерый", "Валеры"),  # §17 base form, not the optional Валер
        ("Юрый", "Юры"),  # §17
        ("Расія", "Расея"),  # §33 з) расейскі (ад Расе[й|а])
        ("расійскі", "расейскі"),
    ],
)
def test_names_with_cited_forms(converter: Converter, nark: str, tarask: str) -> None:
    _both_ways(converter, nark, tarask)


# --- §52 / §72 Заўвага А: еў → эў scope ----------------------------------------------------------
@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        ("Еўропа", "Эўропа"),  # §52
        ("еўрапейскі", "эўрапейскі"),  # §52
        ("Еўклід", "Эўклід"),  # §52 classical name
        ("Еўфрат", "Эўфрат"),  # §52
    ],
)
def test_eu_in_loans_and_classical_names(converter: Converter, nark: str, tarask: str) -> None:
    assert converter.convert(nark, N2T).text == tarask


@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        ("Еўдакія", "Еўдакія"),
        ("Еўдакіі", "Еўдакіі"),
        (
            "Еўфрасіння",
            "Еўфрасіньня",
        ),  # Еў kept; нн → ньн still applies (§40), as the book spells it
    ],
)
def test_eu_kept_in_traditional_christian_names(
    converter: Converter, nark: str, tarask: str
) -> None:
    # §72 Заўвага А: Еўдакія – Аўдоцьця; Е(ў)фрасіньня – Эўфрасіньня (both forms valid)
    assert converter.convert(nark, N2T).text == tarask


# --- country names in case forms --------------------------------------------------------------
REFERENCE_NARKAMAUKA = (
    "краін — Аргенціны, Бельгіі, Арменіі, Германіі, Казахстана, Іспаніі, Кыргызстана, Італіі, "
    "Малдовы, Мексікі, Літвы, Латвіі, Расіі, Польшчы, Украіны, Эстоніі, Швейцарыі і Францыі"
)
#: The project owner's reference sentence. й is optional (§13), so it is compared separately.
REFERENCE_TARASKIEVICA = (
    "краінаў — Аргентыны, Бэльгіі, Армэніі, Нямеччыны, Казахстана, Гішпаніі, Кыргыстана, Італіі, "
    "Малдовы, Мэксыкі, Літвы, Латвіі, Расеі, Польшчы, Украіны, Эстоніі, Швайцарыі і Францыі"
)


def test_country_list_reference(converter: Converter) -> None:
    assert converter.convert(REFERENCE_NARKAMAUKA, N2T).text == REFERENCE_TARASKIEVICA
    aggressive = converter.convert(REFERENCE_NARKAMAUKA, N2T, aggressive=True).text
    assert aggressive.endswith("Швайцарыі й Францыі")
    assert converter.convert(REFERENCE_TARASKIEVICA, T2N).text == REFERENCE_NARKAMAUKA


@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        ("Аргенціна", "Аргентына"),
        ("у Аргенціне", "у Аргентыне"),
        ("Аргенціну", "Аргентыну"),
        ("Арменію", "Армэнію"),
        ("Бельгіяй", "Бэльгіяй"),
        ("з Іспаніі", "з Гішпаніі"),
        ("Кыргызстан", "Кыргыстан"),
        ("у Кыргызстане", "у Кыргыстане"),
        ("Кыргызстанам", "Кыргыстанам"),
        ("у Мексіцы", "у Мэксыцы"),
        ("Мексіку", "Мэксыку"),
        ("Расію", "Расею"),
        ("у Расіі", "у Расеі"),
        ("Германія", "Нямеччына"),
        ("Германію", "Нямеччыну"),
        ("Германіяй", "Нямеччынай"),
    ],
)
def test_country_case_forms(converter: Converter, nark: str, tarask: str) -> None:
    _both_ways(converter, nark, tarask)


@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        ("сталіца Германіі", "сталіца Нямеччыны"),  # genitive (default)
        ("да Германіі", "да Нямеччыны"),  # да + genitive
        ("з Германіі", "з Нямеччыны"),
        ("у Германіі", "у Нямеччыне"),  # у + locative
        ("па Германіі", "па Нямеччыне"),  # па + locative/dative
        ("пры Германіі", "пры Нямеччыне"),
        ("к Германіі", "к Нямеччыне"),  # к + dative
    ],
)
def test_germany_case_chosen_by_preposition(converter: Converter, nark: str, tarask: str) -> None:
    _both_ways(converter, nark, tarask)


def test_germany_bare_dative_is_a_known_limitation(converter: Converter) -> None:
    # No preposition: the genitive is chosen, so a verb-governed dative comes out wrong.
    assert converter.convert("дапамагаць Германіі", N2T).text == "дапамагаць Нямеччыны"


@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        ("з 18 краін", "з 18 краінаў"),  # owner's reference; з stays hard before a number
        ("з краін Еўропы", "з краінаў Эўропы"),
        ("дзясяткі краін", "дзясяткі краінаў"),
        ("краіна", "краіна"),  # only the genitive plural differs
        ("краінам", "краінам"),
    ],
)
def test_krainau_genitive_plural(converter: Converter, nark: str, tarask: str) -> None:
    _both_ways(converter, nark, tarask)
