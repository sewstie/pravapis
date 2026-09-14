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


@pytest.mark.parametrize(
    ("nark", "tarask"),
    [
        # без before an unstressed soft onset produced the non-word *безь
        ("без пісьмовай згоды", "бязь пісьмовай згоды"),
        ("без людзей", "бязь людзей"),
        ("без вялікай мэты", "бязь вялікай мэты"),
    ],
)
def test_bez_never_becomes_bez_soft(converter: Converter, nark: str, tarask: str) -> None:
    there = converter.convert(nark, N2T).text
    assert there == tarask
    assert "безь" not in there
    assert converter.convert(there, T2N).text == nark


def test_convert_particle_bez_soft_unstressed() -> None:
    assert morphology.convert_particle("без", "людзей", N2T) == "бязь"


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


def test_litar_letters_survive_round_trip(converter: Converter) -> None:
    text = "Алфавіт мае 32 літары, а ў словах шмат літар."
    there = converter.convert(text, N2T).text
    assert converter.convert(there, T2N).text == text
