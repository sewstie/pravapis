"""The function-word inventories, now that they are data rather than Python.

These six lists decide what the converter does with particular words. They used to be
constants in `pravapis/rules/morphology.py` and `pravapis/lexicon/case_forms.py`, which
meant a port had no way to obtain them: a rule file can show how softness works, but
nothing in it can show that *цераз* softens and *каля* does not.

Moving data out of code is only worth anything if the behaviour is unchanged and the
file is checked, so that is what these test: the same conversions, the invariants
between the roles, and the failure modes of the reader.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pravapis.pipeline import Converter, context_sensitive
from pravapis.rules.function_words import (
    DECLARED_COLUMNS,
    FUNCTION_WORDS_FILE,
    ROLES,
    SCHEMA_ID,
    FunctionWordError,
    FunctionWords,
    read_function_words,
)
from pravapis.rules.morphology import convert_particle, is_first_syllable_stressed
from pravapis.stress import StressTable
from pravapis.types import Orthography
from tests.conftest import DATA_DIR

PATH = DATA_DIR / FUNCTION_WORDS_FILE


# --- the file ---------------------------------------------------------------------


def test_the_file_declares_its_schema_and_columns() -> None:
    head = [line for line in PATH.read_text(encoding="utf-8").splitlines() if line.startswith("#!")]
    assert f"#!schema {SCHEMA_ID}" in head
    assert "#!columns " + "\t".join(DECLARED_COLUMNS) in head


def test_every_role_is_populated() -> None:
    """A role that lost all its rows is a rule that silently stopped firing."""
    rows = read_function_words(PATH)
    present = {row.role for row in rows}
    assert present == ROLES, f"roles with no rows: {sorted(ROLES - present)}"


def test_every_row_cites_a_section() -> None:
    assert all(row.citation for row in read_function_words(PATH)), (
        "a function word with no § is a claim about the norm with nothing behind it"
    )


def test_a_particle_without_a_target_is_refused(tmp_path: Path) -> None:
    """The row would say a word changes without saying into what."""
    bad = tmp_path / "function_words.tsv"
    bad.write_text("не\tparticle_n2t\t-\tЗбор 2005, §3\n", encoding="utf-8")
    with pytest.raises(FunctionWordError, match="needs a target"):
        read_function_words(bad)


def test_an_unknown_role_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "function_words.tsv"
    bad.write_text("не\tproclitic\tня\tЗбор 2005, §3\n", encoding="utf-8")
    with pytest.raises(FunctionWordError, match="role"):
        read_function_words(bad)


# --- the invariants between roles ---------------------------------------------------


def test_every_softening_preposition_is_also_a_clitic() -> None:
    """Otherwise it counts as a stressed first syllable and drags jakanne onto the next
    word — a wrong output with nothing malformed anywhere in the file."""
    words = FunctionWords.load(DATA_DIR)
    assert words.softening_prepositions <= words.clitics


def test_every_reverse_particle_is_reachable() -> None:
    """A T → N row whose target nothing can produce is a row that never fires."""
    words = FunctionWords.load(DATA_DIR)
    producible = set(words.particles_n2t) | words.softening_prepositions
    assert set(words.particles_t2n.values()) <= producible


def test_context_sensitive_is_derived_not_relisted() -> None:
    """Words whose conversion depends on the next word are never memoised.

    Derived from the inventories on purpose: a particle added to the file but not to a
    second hand-kept list would be cached on its first context and converted wrongly
    everywhere after.
    """
    words = FunctionWords.load(DATA_DIR)
    derived = context_sensitive(words)
    assert set(words.particles_n2t) <= derived
    assert set(words.particles_t2n) <= derived
    assert words.softening_prepositions <= derived


# --- the behaviour, unchanged by the move -------------------------------------------


@pytest.mark.parametrize(
    ("word", "following", "expected"),
    [
        ("не", "быў", "ня"),  # §3 jakanne before a stressed first syllable
        ("не", "было", None),  # stress on the second syllable, so не stays
        ("без", "крыўды", "бяз"),
        ("з", "вераю", "зь"),  # §29 softening preposition
    ],
)
def test_particles_still_convert(
    word: str, following: str, expected: str | None, stress: StressTable
) -> None:
    words = FunctionWords.load(DATA_DIR)
    got = convert_particle(
        word,
        following,
        Orthography.TARASKIEVICA,
        stress,
        None,
        words,
    )
    assert got == expected


def test_a_clitic_is_never_a_stressed_first_syllable() -> None:
    words = FunctionWords.load(DATA_DIR)
    assert not is_first_syllable_stressed("з", None, words)
    assert not is_first_syllable_stressed("на", None, words)


def test_an_empty_inventory_fires_nothing() -> None:
    """The opt-out, stated so it stays an explicit act rather than a default."""
    empty = FunctionWords.empty()
    assert convert_particle("не", "быў", Orthography.TARASKIEVICA, None, None, empty) is None
    assert convert_particle("ня", None, Orthography.NARKAMAUKA, None, None, empty) is None


def test_forgetting_the_argument_uses_the_shipped_inventory() -> None:
    """The default is the shipped data, not an empty set.

    An empty default would make every caller that omits the argument silently stop
    converting, which is the one failure this module cannot detect from the inside.
    """
    assert convert_particle("ня", None, Orthography.NARKAMAUKA) == "не"


def test_the_converter_reads_them_from_its_data_directory(converter: Converter) -> None:
    assert converter.function_words.particles_n2t == {"не": "ня", "без": "бяз"}
    assert "умбры" in converter.function_words.stressed_initial_u
    text = converter.convert("Ён не хоча без слёз.", Orthography.TARASKIEVICA).text
    assert text == "Ён ня хоча бязь сьлёз."


def test_the_case_table_still_picks_a_column_by_preposition(converter: Converter) -> None:
    """`dative_locative_preposition` moved out of case_forms.py in the same pass."""
    assert converter.convert("у Германіі", Orthography.TARASKIEVICA).text == "у Нямеччыне"
    assert converter.convert("сталіца Германіі", Orthography.TARASKIEVICA).text == (
        "сталіца Нямеччыны"
    )
