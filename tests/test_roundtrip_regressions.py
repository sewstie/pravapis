"""Round-trip failures mined by scripts/mine_roundtrip.py, pinned once fixed.

Each case broke N→T→N (or produced a non-word on the way there). They come
from data/eval/roundtrip_corpus.txt, never from the gold set.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from belnorm.lexicon.store import Lexicon
from belnorm.pipeline import Converter
from belnorm.rules import loanwords, morphology
from belnorm.stress import StressTable
from belnorm.types import Orthography

N2T = Orthography.TARASKIEVICA
T2N = Orthography.NARKAMAUKA


@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        # palatalization: unassim must run before ungeminate (found by hypothesis)
        ("зллю", "зьльлю"),
        # loan.l_palatalization had no reverse rule
        ("лабараторыі", "лябараторыі"),
        ("дыпламатыя", "дыпляматыя"),
        ("тэхналогій", "тэхналёгій"),
        ("тэрміналогіяй", "тэрміналёгіяй"),
        ("класаў", "клясаў"),
        # класічны got only the л half of its adaptation and could not come back
        ("класічнага", "клясычнага"),
        ("Класікі", "Клясыкі"),
        # loan.i_to_y had no reverse rule
        ("сінагогу", "сынагогу"),
        ("сінонімы", "сынонімы"),
        ("сістэму", "сыстэму"),
        ("сінтэзу", "сынтэзу"),
    ],
)
def test_word_round_trips(converter: Converter, nark: str, tarask: str) -> None:
    there = converter.convert(nark, N2T).text
    assert there == tarask
    assert converter.convert(there, T2N).text == nark


#: Examples quoted from Збор правілаў 2005 (§3 jakanne, §29 softness of prepositions,
#: §29 Заўвага А unstressed initial і), plus our own cases derived from those rules.
CODIFICATION_CLITICS = [
    # §3: не / без in the syllable right before the stress
    ("не пойдзе", "ня пойдзе"),  # ня по´йдзе
    ("без крыўды", "бяз крыўды"),  # бяз кры´ўды
    ("не было", "не было"),  # было´: second syllable, no jakanne (endnote xxxi)
    # §29: softness extends to з, без/бяз, праз, цераз
    ("з вераю", "зь вераю"),
    ("без слёз", "бязь сьлёз"),
    ("праз лес", "празь лес"),
    ("цераз сетку", "церазь сетку"),
    ("з юнаком", "зь юнаком"),
    ("без іх", "бязь іх"),  # бязь і´х: stressed initial і
    ("з Інаю", "зь Інаю"),
    ("без Янкі", "бязь Янкі"),
    ("без яго", "безь яго"),  # the book's own prose: "безь яго"
    # §29 Заўвага А: no softening before an unstressed initial і
    ("з ідэяй", "з ідэяй"),
    ("без іголкі", "без іголкі"),
    ("праз імглу", "праз імглу"),
    # §29: no softening before г, к, х
    ("без кішэні", "без кішэні"),
    # unstressed без before a soft onset: безь (no jakanne, but softness)
    ("без пісьмовай згоды", "безь пісьмовай згоды"),
    ("без людзей", "безь людзей"),
    ("без вялікай мэты", "безь вялікай мэты"),
    ("без якога", "безь якога"),
    ("без ліку", "бязь ліку"),  # лі+ку: stressed and soft
]


@pytest.mark.parametrize(("nark", "tarask"), CODIFICATION_CLITICS)
def test_clitics_follow_codification(converter: Converter, nark: str, tarask: str) -> None:
    there = converter.convert(nark, N2T).text
    assert there == tarask
    assert converter.convert(there, T2N).text == nark


@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        # The soft-onset test read the Narkamaŭka form (слёз: no written softness)
        # instead of the Taraškievica one (сьлёз). Fixed by converting the next word first.
        ("без слёз", "бязь сьлёз"),
        ("з снегам", "зь сьнегам"),
        ("праз свет", "празь сьвет"),
        ("цераз сцяну", "церазь сьцяну"),
        # softness already visible in Narkamaŭka keeps working
        ("з цёртай бульбы", "зь цёртай бульбы"),
        ("з ім", "зь ім"),
        # hard onset in both orthographies stays hard
        ("з сабой", "з сабой"),
        ("без працы", "бяз працы"),
    ],
)
def test_soft_onset_reads_taraskievica_form(converter: Converter, nark: str, tarask: str) -> None:
    there = converter.convert(nark, N2T).text
    assert there == tarask
    assert converter.convert(there, T2N).text == nark


def test_convert_particle_soft_onset_uses_next_target(stress: StressTable) -> None:
    # stress from the Narkamaŭka form (слёз is monosyllabic), softness from the Taraškievica form
    assert morphology.convert_particle("без", "слёз", N2T, stress) == "бяз"
    assert morphology.convert_particle("без", "слёз", N2T, stress, "сьлёз") == "бязь"
    assert morphology.convert_particle("з", "снегам", N2T, stress, "сьнегам") == "зь"


def test_convert_particle_bez_unstressed_softens(stress: StressTable) -> None:
    # §29: без/бяз both soften; jakanne (§3) did not apply, so the vowel stays е
    assert morphology.convert_particle("без", "людзей", N2T, stress, "людзей") == "безь"
    # §29 Заўвага А: unstressed initial і — no softening
    assert morphology.convert_particle("з", "ідэяй", N2T, stress, "ідэяй") is None


def test_every_forward_loan_stem_has_a_reverse() -> None:
    skipped = loanwords._L_REVERSE_SKIP | loanwords._I_REVERSE_SKIP
    for rules, forward, reverse in (
        (loanwords._L_RULES, loanwords.apply_l_palatalization, loanwords.remove_l_palatalization),
        (loanwords._I_RULES, loanwords.apply_i_to_y, loanwords.remove_i_to_y),
    ):
        for pattern, repl in rules:
            if repl in skipped:
                continue
            # a sample word: the stem with its capture groups dropped, plus an ending
            stem = pattern.pattern.lstrip("^").split("(?")[0]
            stem = stem.replace("(а|апа|кампа|экспа|прапа|дыспа|пра)?", "")
            word = {"логі": "біялогія"}.get(stem, stem + "а")
            if forward(word) == word:
                continue  # the lookahead excludes this synthetic ending
            assert reverse(forward(word)) == word, (pattern.pattern, word)


def test_salty_is_not_a_salon() -> None:
    assert loanwords.remove_l_palatalization("салёны") == "салёны"


def test_one_way_lexicon_entries(tmp_path: Path) -> None:
    tsv = tmp_path / "lex.tsv"
    tsv.write_text("літр\tлітар\tn2t\nклас\tкляса\n", encoding="utf-8")
    lex = Lexicon.load(tsv)
    assert lex.lookup("літр", N2T) == "літар"
    # Taraškievica літар is also the genitive plural of літара: no reverse key.
    assert lex.lookup("літар", T2N) is None
    assert lex.lookup("кляса", T2N) == "клас"


def test_bad_direction_flag_is_rejected(tmp_path: Path) -> None:
    from belnorm.lexicon.builder import read_tsv_pairs

    tsv = tmp_path / "lex.tsv"
    tsv.write_text("літр\tлітар\tboth\n", encoding="utf-8")
    with pytest.raises(ValueError, match="n2t or t2n"):
        list(read_tsv_pairs(tsv))


SWITZERLAND = [
    ("Швейцарыя", "Швайцарыя"),
    ("Швейцарыі", "Швайцарыі"),
    ("Швейцарыю", "Швайцарыю"),
    ("Швейцарыяй", "Швайцарыяй"),
    ("Швейцарыяю", "Швайцарыяю"),
    ("швейцарскі", "швайцарскі"),
    ("швейцарскага", "швайцарскага"),
    ("швейцарскаму", "швайцарскаму"),
    ("швейцарскім", "швайцарскім"),
    ("швейцарскае", "швайцарскае"),
    ("швейцарская", "швайцарская"),
    ("швейцарскай", "швайцарскай"),
    ("швейцарскую", "швайцарскую"),
    ("швейцарскаю", "швайцарскаю"),
    ("швейцарскія", "швайцарскія"),
    ("швейцарскіх", "швайцарскіх"),
    ("швейцарскімі", "швайцарскімі"),
]


@pytest.mark.parametrize(("nark", "tarask"), SWITZERLAND)
def test_switzerland_all_forms(converter: Converter, nark: str, tarask: str) -> None:
    assert converter.convert(nark, N2T).text == tarask
    assert converter.convert(tarask, T2N).text == nark


def test_unresolved_and_unrelated_words_pass_through(converter: Converter) -> None:
    # Кыргызстан: sources disagree (NORMS.md, "Unresolved"); швейцар: a different lexeme.
    for word in ("Кыргызстан", "Кыргызстана", "швейцар", "швейцара"):
        assert converter.convert(word, N2T).text == word


def test_litar_letters_survive_round_trip(converter: Converter) -> None:
    text = "Алфавіт мае 32 літары, а ў словах шмат літар."
    there = converter.convert(text, N2T).text
    assert converter.convert(there, T2N).text == text
