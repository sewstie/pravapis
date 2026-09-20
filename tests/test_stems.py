"""The stem etymology inventory: parsing, longest match, gating, and the derived reverse.

The converter's headline guard is its false-positive rate, and the stem inventory is
the only thing standing between the loanword rules and every native word that happens
to share a letter pattern. These tests are that guard's unit tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pravapis.lexicon.stems import (
    ALTERNATIONS,
    Provenance,
    StemError,
    StemIndex,
    StemMatch,
    WordClass,
    read_stem_sources,
    read_stems,
    validate_stems,
)
from pravapis.pipeline import Converter
from pravapis.rules.engine import RuleEngine
from pravapis.rules.loanwords import derive_target_entries, reverse_collisions, target_stem
from pravapis.types import Orthography

N2T = Orthography.TARASKIEVICA
T2N = Orthography.NARKAMAUKA

DATA = Path(__file__).resolve().parent.parent / "data" / "lexicon" / "stems"


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "stems.tsv"
    path.write_text(body, encoding="utf-8")
    return path


# --- parsing -----------------------------------------------------------------------------
def test_reads_the_five_required_columns(tmp_path: Path) -> None:
    (entry,) = read_stems(_write(tmp_path, "план\tloan\tl\t§55.1\tcited\n"))
    assert entry.stem == "план"
    assert entry.cls is WordClass.LOAN
    assert entry.alternations == {"l"}
    assert entry.provenance is Provenance.CITED
    assert entry.anchored
    assert entry.target is None


def test_leading_dash_marks_an_unanchored_stem(tmp_path: Path) -> None:
    (entry,) = read_stems(_write(tmp_path, "-логі\tloan\tl\t§55.1\tcited\n"))
    assert entry.stem == "логі"
    assert not entry.anchored


def test_sixth_column_is_an_explicit_target(tmp_path: Path) -> None:
    (entry,) = read_stems(_write(tmp_path, "каланіял\tloan\t-\t§55.1\tcited\tкалёніял\n"))
    assert entry.target == "калёніял"
    assert target_stem(entry) == "калёніял"


def test_alternation_may_be_restricted_to_one_direction(tmp_path: Path) -> None:
    (entry,) = read_stems(_write(tmp_path, "салон\tloan\tl:n2t\t§55.1\tcited\n"))
    assert entry.alternations == {"l"}
    assert entry.forward_only == {"l"}


@pytest.mark.parametrize(
    "line",
    [
        "план\tloan\tl\t§55.1\n",  # too few columns
        "план\tspanish\tl\t§55.1\tcited\n",  # unknown class
        "план\tloan\tl\t§55.1\tprobably\n",  # unknown provenance
        "план\tloan\tzz\t§55.1\tcited\n",  # unknown alternation
        "план\tloan\tl:sideways\t§55.1\tcited\n",  # unknown restriction
        "лапа\tnative\tl\t-\tcited\n",  # a native stem licenses nothing
    ],
)
def test_malformed_rows_are_rejected(tmp_path: Path, line: str) -> None:
    with pytest.raises(StemError):
        list(read_stems(_write(tmp_path, line)))


def test_comments_and_blank_lines_are_skipped(tmp_path: Path) -> None:
    body = "# a comment\n\nплан\tloan\tl\t§55.1\tcited\n\n"
    assert len(list(read_stems(_write(tmp_path, body)))) == 1


# --- matching ----------------------------------------------------------------------------
def test_longest_match_wins_over_class(tmp_path: Path) -> None:
    """The whole false-friend mechanism: a longer native stem beats a shorter loan one."""
    index = StemIndex(
        read_stems(_write(tmp_path, "клас\tloan\tl\t§55.1\tcited\nкласц\tnative\t-\t-\tcited\n"))
    )
    loan = index.match("класны")
    native = index.match("класці")
    assert loan is not None and loan.cls is WordClass.LOAN
    assert native is not None and native.cls is WordClass.NATIVE


def test_unanchored_stems_match_inside_the_word(tmp_path: Path) -> None:
    index = StemIndex(read_stems(_write(tmp_path, "-логі\tloan\tl\t§55.1\tcited\n")))
    match = index.match("біялогія")
    assert match is not None
    assert (match.start, match.end) == (3, 7)


def test_uncertain_rows_are_parsed_but_never_indexed(tmp_path: Path) -> None:
    body = "ганак\tloan\tg\tUNVERIFIED\tuncertain\nплан\tloan\tl\t§55.1\tcited\n"
    entries = list(read_stems(_write(tmp_path, body)))
    assert len(entries) == 2
    index = StemIndex(entries)
    assert index.match("ганак") is None
    assert index.match("план") is not None


def test_match_allows_only_licensed_alternations(tmp_path: Path) -> None:
    index = StemIndex(read_stems(_write(tmp_path, "версі\tloan\te\t§11б\tcited\n")))
    match = index.match("версія")
    assert match is not None
    assert match.allows("e")
    assert not match.allows("i")  # вэрсія, never вэрсыя


def test_native_match_allows_nothing() -> None:
    match = StemMatch("лап", WordClass.NATIVE, frozenset({"l"}), 0, 3)
    assert not match.allows("l")


# --- the derived reverse index -----------------------------------------------------------
def test_reverse_keys_are_derived_from_the_forward_ones(tmp_path: Path) -> None:
    entries = list(read_stems(_write(tmp_path, "сезон\tloan\te\t§11б\tcited\n")))
    reverse = {e.stem: e.target for e in derive_target_entries(entries)}
    assert reverse["сэзон"] == "сезон"


def test_forward_only_stems_get_no_reverse_entry(tmp_path: Path) -> None:
    """салён- is also the native adjective "salty", so the reverse is left alone."""
    entries = list(read_stems(_write(tmp_path, "салон\tloan\tl:n2t\t§55.1\tcited\n")))
    assert [e.stem for e in derive_target_entries(entries)] == []


def test_reverse_index_also_carries_assimilative_softness(tmp_path: Path) -> None:
    """Real Taraškievica writes бізьнэс, and softness is marked before the loan rules run."""
    entries = list(read_stems(_write(tmp_path, "бізнес\tloan\te\t§11б\tcited\n")))
    assert "бізьнэс" in {e.stem for e in derive_target_entries(entries)}


def test_collisions_are_reported(tmp_path: Path) -> None:
    body = "десерт\tloan\te\t§11б\tcited\nдэсерт\tloan\te\t§11б\tcited\n"
    assert reverse_collisions(list(read_stems(_write(tmp_path, body))))


# --- the shipped inventory ---------------------------------------------------------------
def test_shipped_inventory_is_valid() -> None:
    entries = read_stem_sources(DATA)
    assert not validate_stems(entries)
    assert not reverse_collisions(entries)


def test_shipped_inventory_has_both_classes() -> None:
    entries = [e for e in read_stem_sources(DATA) if e.applied]
    classes = {e.cls for e in entries}
    assert classes == {WordClass.LOAN, WordClass.NATIVE}


def test_every_loan_stem_cites_something() -> None:
    for e in read_stem_sources(DATA):
        if e.cls is WordClass.LOAN and e.provenance is not Provenance.UNCERTAIN:
            assert e.source, e.stem


def test_every_alternation_code_is_known() -> None:
    for e in read_stem_sources(DATA):
        assert e.alternations <= ALTERNATIONS, e.stem


# --- gating, end to end ------------------------------------------------------------------
@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("сезон", "сэзон"),
        ("версія", "вэрсія"),
        ("аперацыя", "апэрацыя"),
        ("дакумент", "дакумэнт"),
        ("план", "плян"),
        ("сістэма", "сыстэма"),
    ],
)
def test_loan_words_convert(engine: RuleEngine, word: str, expected: str) -> None:
    assert engine.apply(word, N2T)[0] == expected


@pytest.mark.parametrize("word", ["мера", "серада", "неба", "месяц", "сіла", "лапа", "вера"])
def test_native_words_are_left_alone(engine: RuleEngine, word: str) -> None:
    assert not [r for r in engine.apply(word, N2T)[1] if r.startswith("loan.")]


@pytest.mark.parametrize(
    ("word", "expected"),
    [("сэзон", "сезон"), ("вэрсія", "версія"), ("плян", "план"), ("сыстэма", "сістэма")],
)
def test_loan_words_convert_back(engine: RuleEngine, word: str, expected: str) -> None:
    assert engine.apply(word, T2N)[0] == expected


def test_suffix_outside_the_stem_is_untouched(engine: RuleEngine) -> None:
    """§66: марксізм keeps its і, because the stem is маркс and the suffix is out of span."""
    assert engine.apply("марксізм", N2T)[0] == "марксізм"


# --- collisions found against GrammarDB, not against the gold set -------------------------
@pytest.mark.parametrize(
    ("word", "unchanged"),
    [
        # клуб- is a native root as well as a loan: клубень "tuber".
        ("клубень", True),
        ("клубеньчык", True),
        ("клубасты", True),
        ("клубануць", True),
        ("салонец", True),  # a soil type, not a drawing room
        # ...but the loan must still convert, including its case forms.
        ("клуб", False),
        ("клубе", False),
        ("клубам", False),
        ("салон", False),
    ],
)
def test_grammardb_collisions_stay_guarded(engine: RuleEngine, word: str, unchanged: bool) -> None:
    """Found by scripts/check_stem_collisions.py; the gold set never reached these."""
    fired = [r for r in engine.apply(word, N2T)[1] if r.startswith("loan.")]
    assert (not fired) is unchanged, (word, fired)


def test_load_bearing_guards_are_pinned(engine: RuleEngine) -> None:
    """Of 55 native guards only a handful change an answer; these are they.

    If one stops mattering a loan stem has moved; if a new word joins the list, a loan
    stem has grown teeth. Either way it should be a deliberate edit, not a surprise.
    """
    for word in ("класці", "падлогі", "клубок", "клубень", "салонец"):
        fired = [r for r in engine.apply(word, N2T)[1] if r.startswith("loan.")]
        assert not fired, (word, fired)


# --- ґ: licensed by зноска 55, declined by the project -------------------------------------
@pytest.mark.parametrize("word", ["ганак", "гузік", "гвалт", "агрэст", "цуглі", "швагер"])
def test_g_is_never_produced(converter: Converter, word: str) -> None:
    """Зноска 55 licenses ґ in exactly these words and the alphabet marks the letter
    факультатыўна — so both spellings are valid and the choice is the project's. It
    writes г, in every mode. See data/NORMS.md, "Project decision: no ґ".
    """
    assert converter.convert(word, N2T).text == word
    assert converter.variant(True).convert(word, N2T).text == word


@pytest.mark.parametrize("word", ["ґанак", "аґрэст", "цуґлі", "Ґілмарам"])
def test_g_in_the_input_is_normalised_away(converter: Converter, word: str) -> None:
    """Text arriving with ґ is brought back to г rather than passed through."""
    assert "ґ" not in converter.convert(word, T2N).text


@pytest.mark.parametrize("word", ["гара", "гуска", "горад", "гадзіна"])
def test_native_g_words_are_untouched_even_aggressively(converter: Converter, word: str) -> None:
    assert converter.variant(True).convert(word, N2T).text == word
