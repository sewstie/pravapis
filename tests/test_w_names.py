"""The W-name inventory, and the rule that no longer consults it.

`data/names/w_names.tsv` was mined to answer a question the project turned out to have
answered wrongly: whether Narkamaŭka keeps the Ў in names that render English *W*. It
does not — Правілы 2008 §15 п.4 says a proper name is *always* written with У складовае
and no breve — so T → N reverses the Ў unconditionally and reads no list at all.

The file is still shipped, still under the data version, still schema-checked. It is
evidence about which names these are, and the forward direction may yet want it. These
tests hold both halves in place: the file stays well-formed, and the converter stays off
it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pravapis.pipeline import Converter
from pravapis.rules.morphology import initial_w_to_u
from pravapis.rules.w_names import (
    DECLARED_COLUMNS,
    SCHEMA_ID,
    W_NAMES_FILE,
    WNameError,
    WNames,
    read_w_names,
)
from pravapis.types import Orthography
from tests.conftest import DATA_DIR

W_NAMES_PATH = DATA_DIR / W_NAMES_FILE


# --- the file ---------------------------------------------------------------------


def test_the_shipped_inventory_parses() -> None:
    rows = read_w_names(W_NAMES_PATH)
    assert rows, "the inventory is empty"
    assert all(row.stem.startswith("ў") for row in rows)
    assert all(row.evidence for row in rows), "every row must say what backs it"


def test_the_file_declares_its_schema_and_columns() -> None:
    """A port reads the declaration, not this module, to learn the column order."""
    head = [
        line
        for line in W_NAMES_PATH.read_text(encoding="utf-8").splitlines()
        if line.startswith("#!")
    ]
    assert f"#!schema {SCHEMA_ID}" in head
    assert "#!columns " + "\t".join(DECLARED_COLUMNS) in head


def test_the_hand_rows_survived_mining() -> None:
    """Mining must never drop a stem that came from an attested sentence.

    `scripts/mine_w_names.py` rewrites this file wholesale from a Wikidata query, and
    the hand rows are the ones a person read off real text. A mining run that silently
    replaced them would be a loss of evidence disguised as an update.
    """
    hand = {row.stem for row in read_w_names(W_NAMES_PATH) if row.provenance == "hand"}
    assert {"ўіл", "ўотэр", "ўэлт", "ўэйлз", "ўайлд"} <= hand


def test_mining_found_names_the_gold_set_never_attested() -> None:
    mined = {row.stem for row in read_w_names(W_NAMES_PATH) if row.provenance == "wikidata"}
    assert len(mined) > 10, "mining contributed almost nothing — check the query"


def test_a_stem_that_cannot_match_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "w_names.tsv"
    bad.write_text("уіл\thand\tno leading ў\n", encoding="utf-8")
    with pytest.raises(WNameError, match="does not begin with"):
        read_w_names(bad)


def test_an_unknown_provenance_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "w_names.tsv"
    bad.write_text("ўіл\tguessed\tsomewhere\n", encoding="utf-8")
    with pytest.raises(WNameError, match="provenance"):
        read_w_names(bad)


def test_the_inventory_loads_from_the_data_directory() -> None:
    assert len(WNames.load(DATA_DIR)) > 10
    assert "ўіл" in WNames.load(DATA_DIR)
    assert "ўкраіна" not in WNames.load(DATA_DIR)


# --- the rule ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        # Правілы 2008 §15 п.4: a proper name never begins with Ў in Narkamaŭka. That
        # holds for §18's own examples and for the English W-names alike — the rule is
        # categorical and draws no distinction between them.
        ("Ўкраіны", "Украіны"),
        ("Ўфе", "Уфе"),
        ("Ўіл", "Уіл"),
        ("Ўотэрзам", "Уотэрзам"),
        ("Ўэйлзу", "Уэйлзу"),
        # §18 Заўвага: a hyphen is not a punctuation mark, so each part is judged.
        ("Кука-Ўітсан", "Кука-Уітсан"),
        # Lowercase ў is the same in both orthographies and is left alone.
        ("ўніверсітэце", None),
        ("ўзняліся", None),
        # An all-caps token is an abbreviation, not a word beginning with у.
        ("ЗНАКАЎ", None),
        # Nothing to do.
        ("Украіны", None),
    ],
)
def test_narkamauka_never_starts_a_name_with_u_breve(word: str, expected: str | None) -> None:
    assert initial_w_to_u(word) == expected


def test_the_reversal_does_not_depend_on_what_precedes_it() -> None:
    """The asymmetry between the two codifications, stated as a test.

    §18 makes У → Ў conditional (after a vowel, unstressed, capitalised); §15 п.4 makes
    the reverse unconditional. A future refactor that "restores the symmetry" by giving
    this rule the previous word again would reintroduce the bug this replaced: *Разумнік
    Ўіл*, where the previous word ends in a consonant, would keep its Ў.
    """
    converter = Converter.from_config(None)
    after_consonant = converter.convert("Разумнік Ўіл Гантынг", Orthography.NARKAMAUKA).text
    after_vowel = converter.convert("школу Ўайлд Лэйк", Orthography.NARKAMAUKA).text
    assert after_consonant == "Разумнік Уіл Гантынг"
    assert after_vowel == "школу Уайлд Лэйк"


def test_the_converter_does_not_read_the_inventory(converter: Converter) -> None:
    """The inventory is shipped, but nothing in the conversion path consults it.

    Asserted rather than assumed: the file is still here and still validated, so the
    only thing keeping it out of the cascade is that no code reads it.
    """
    assert not hasattr(converter, "w_names")


def test_section_18_still_round_trips(converter: Converter) -> None:
    """N → T → N is the property that matters, and §15 п.4 leaves it intact.

    T → N → T does not round-trip for these names (Ўіл → Уіл → Уіл) and never could:
    Taraškievica's Ў carries information Narkamaŭka does not write down. The project's
    round-trip property is N → T → N, which is unaffected.
    """
    for text in ("сталіца Украіны", "ва Уфе", "Разумнік Уіл Гантынг"):
        there = converter.convert(text, Orthography.TARASKIEVICA).text
        assert converter.convert(there, Orthography.NARKAMAUKA).text == text
