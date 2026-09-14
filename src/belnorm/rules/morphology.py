"""Context-dependent clitics and small morphological rules.

Taraškievica spells the particle *не* and the preposition *без* as *ня* /
*бяз* when the following word is stressed on its first syllable, and softens
prepositions ending in *з* before a soft onset (*з ім* → *зь ім*,
*без мяне* → *бязь мяне*). Both need the next word, so they run in the
pipeline rather than the per-word rule engine.

Stress is not marked in Belarusian text. The heuristic here — the next word
is monosyllabic, or sits in a small list of common first-syllable-stressed
words — covers the frequent cases and is deliberately conservative; the rest
is the classifier's job.
"""

from __future__ import annotations

from typing import Final

from belnorm.rules.palatalization import SOFT_TRIGGERS, SOFT_VOWELS, SOFTENERS
from belnorm.types import Orthography

VOWELS: Final[frozenset[str]] = frozenset("аеёіоуыэюя")

#: не/без → ня/бяз (N→T) and back (T→N).
PARTICLES_N2T: Final[dict[str, str]] = {"не": "ня", "без": "бяз"}
PARTICLES_T2N: Final[dict[str, str]] = {"ня": "не", "бяз": "без", "бязь": "без", "зь": "з"}

#: Prepositions ending in з that soften before a soft onset.
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

#: Common polysyllabic words stressed on the first syllable.
FIRST_SYLLABLE_STRESS: Final[frozenset[str]] = frozenset(
    [
        "мяне",
        "цябе",
        "сябе",
        "гэта",
        "гэты",
        "гэтая",
        "гэтае",
        "гэтыя",
        "гэтак",
        "гэтым",
        "гэтага",
        "толькі",
        "вельмі",
        "трэба",
        "нават",
        "можа",
        "можаш",
        "можам",
        "мог",
        "магу",
        "магла",
        "маглі",
        "могуць",
        "хоча",
        "хочу",
        "хочаш",
        "хочам",
        "хочуць",
        "буду",
        "будзе",
        "будзеш",
        "будзем",
        "будуць",
        "было",
        "была",
        "былі",
        "быў",
        "ведаю",
        "ведае",
        "ведаеш",
        "ведаем",
        "ведаюць",
        "ведаў",
        "ведала",
        "ведалі",
        "мае",
        "маю",
        "маеш",
        "маем",
        "маюць",
        "мела",
        "меў",
        "мелі",
        "стаў",
        "стала",
        "сталі",
        "стане",
        "станеш",
        "станем",
        "стануць",
        "бачу",
        "бачыў",
        "бачыла",
        "бачылі",
        "чую",
        "чуў",
        "чула",
        "чулі",
        "знае",
        "знаю",
        "знаеш",
        "знаем",
        "знаюць",
        "кажа",
        "кажу",
        "кажаш",
        "кажам",
        "кажуць",
        "люблю",
        "любіць",
        "любіш",
        "любім",
        "любяць",
        "помню",
        "помніць",
        "помніш",
        "помнім",
        "помняць",
        "верыць",
        "веру",
        "верыш",
        "верым",
        "вераць",
        "хочацца",
        "дома",
    ]
)


def syllable_count(word: str) -> int:
    return sum(1 for c in word if c in VOWELS)


def is_first_syllable_stressed(word: str) -> bool:
    """Heuristic: monosyllabic content word, or a known first-stressed word."""
    word = word.lower()
    if word in CLITICS:
        return False
    if syllable_count(word) == 1:
        return True
    return word in FIRST_SYLLABLE_STRESS


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


def convert_particle(word: str, next_word: str | None, direction: Orthography) -> str | None:
    """Rewrite a clitic given the word that follows it; None when no rule applies.

    Input is lowercase. Returns the fully converted form (including the soft
    sign on *бязь* / *зь*), so the caller can skip the per-word engine for it.
    """
    if direction is Orthography.NARKAMAUKA:
        return PARTICLES_T2N.get(word)

    result: str | None = None
    if word in PARTICLES_N2T and next_word is not None and is_first_syllable_stressed(next_word):
        result = PARTICLES_N2T[word]
    base = result or word
    if base in SOFTENING_PREPOSITIONS and next_word is not None and _soft_onset(next_word.lower()):
        result = base + "ь"
    return result
