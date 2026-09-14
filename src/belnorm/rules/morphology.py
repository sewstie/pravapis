"""Context-dependent clitics (Збор правілаў 2005, §3 and §29).

Jakanne (§3): the particle *не* and the preposition *без* become *ня* / *бяз*
when they stand in the syllable right before the stress, i.e. when the next
word is stressed on its first syllable: *ня наш, ня по´йдзе, бяз кры´ўды*.
*не было́* stays *не*: the stress is on the second syllable.

Assimilative softness (§29) extends to the prepositions *з, без/бяз, праз,
цераз* before a soft onset, whether or not jakanne applied: *зь вераю, бязь
сьлёз, празь лес, церазь сетку; безь яго*. §29 Заўвага А: before an
*unstressed* initial *і* no [й] develops, so there is no softening: *з ідэяй,
без іголкі, праз імглу* — but *бязь і´х, зь І´наю* when the і is stressed.

Both need the next word, so they run in the pipeline rather than the per-word
rule engine. Stress is not written in Belarusian text; it comes from GrammarDB
stress marks (``belnorm.stress.StressTable``). Without a table only two facts
are used: a monosyllabic content word is stressed on its only syllable, and ё
is always stressed. Anything else counts as not first-stressed.
"""

from __future__ import annotations

from typing import Final

from belnorm.rules.palatalization import SOFT_TRIGGERS, SOFT_VOWELS, SOFTENERS
from belnorm.stress import StressTable
from belnorm.types import Orthography

VOWELS: Final[frozenset[str]] = frozenset("аеёіоуыэюя")

#: не/без → ня/бяз (N→T) and back (T→N).
PARTICLES_N2T: Final[dict[str, str]] = {"не": "ня", "без": "бяз"}
PARTICLES_T2N: Final[dict[str, str]] = {
    "ня": "не",
    "бяз": "без",
    "бязь": "без",
    "безь": "без",
    "зь": "з",
}

#: Prepositions that soften before a soft onset (§29): з, без/бяз, праз, цераз.
SOFTENING_PREPOSITIONS: Final[frozenset[str]] = frozenset({"з", "без", "бяз", "праз", "цераз"})

#: Unstressed function words: a monosyllable here does not attract "ня"/"бяз".
CLITICS: Final[frozenset[str]] = frozenset(
    [
        "у",
        "ў",
        "з",
        "зь",
        "на",
        "да",
        "па",
        "за",
        "аб",
        "ад",
        "пра",
        "і",
        "й",
        "ды",
        "а",
        "ці",
        "б",
        "бы",
        "ж",
        "жа",
        "не",
        "ня",
        "без",
        "бяз",
        "для",
        "пад",
        "над",
        "праз",
        "цераз",
        "к",
        "аж",
        "бо",
        "то",
        "ні",
    ]
)


def syllable_count(word: str) -> int:
    return sum(1 for c in word.lower() if c in VOWELS)


def is_first_syllable_stressed(word: str, stress: StressTable | None = None) -> bool:
    """Is ``word`` stressed on its first syllable?

    GrammarDB stress marks when a table is given; otherwise (and for words the
    table does not know) only monosyllables and a leading ё count.
    """
    if word.lower() in CLITICS:
        return False
    if stress is not None and stress.is_first_stressed(word):
        return True
    lw = word.lower()
    if syllable_count(lw) == 1:
        return True
    # ё is always stressed, so a word whose first vowel is ё is first-stressed.
    return next((c for c in lw if c in VOWELS), "") == "ё"


def _soft_onset(word: str) -> bool:
    """Does ``word`` begin with a soft consonant or a soft vowel?"""
    if not word:
        return False
    if word[0] in SOFT_VOWELS:
        return True
    head = word[:2] if word[:2] == "дз" else word[0]
    if head not in SOFT_TRIGGERS:
        return False
    return word[len(head) : len(head) + 1] in set(SOFTENERS)


def convert_particle(
    word: str,
    next_word: str | None,
    direction: Orthography,
    stress: StressTable | None = None,
    next_target: str | None = None,
) -> str | None:
    """Rewrite a clitic given the word that follows it; None when no rule applies.

    Input is lowercase. Returns the fully converted form (including the soft
    sign on *бязь* / *зь*), so the caller can skip the per-word engine for it.

    The two conditions read *different* forms of the next word:

    - stress (jakanne) reads ``next_word``, the Narkamaŭka form, because the
      stress table is built from GrammarDB, which is Narkamaŭka;
    - soft onset reads ``next_target``, the next word already converted to
      Taraškievica, because only there is assimilative softness written:
      Narkamaŭka *слёз* shows no soft с, Taraškievica *сьлёз* does. Reading
      the Narkamaŭka form is the без слёз → *бяз сьлёз bug. Without
      ``next_target`` the Narkamaŭka form is the fallback.
    """
    if direction is Orthography.NARKAMAUKA:
        return PARTICLES_T2N.get(word)

    result: str | None = None
    if (
        word in PARTICLES_N2T
        and next_word is not None
        and is_first_syllable_stressed(next_word, stress)
    ):
        result = PARTICLES_N2T[word]
    base = result or word
    onset_form = next_target if next_target is not None else next_word
    if (
        base in SOFTENING_PREPOSITIONS
        and next_word is not None
        and onset_form is not None
        and _soft_onset(onset_form.lower())
        and not _unstressed_initial_i(next_word, stress)
    ):
        result = base + "ь"
    return result


def _unstressed_initial_i(word: str, stress: StressTable | None) -> bool:
    """§29 Заўвага А: an unstressed initial і develops no [й], so з/без/праз stay hard.

    Reads the Narkamaŭka form (stress comes from GrammarDB); the letter і is the
    same in both orthographies.
    """
    return word[:1].lower() == "і" and not is_first_syllable_stressed(word, stress)
