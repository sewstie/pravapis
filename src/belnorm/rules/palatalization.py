"""Assimilative softness (асіміляцыйная мяккасьць).

Taraškievica writes the soft sign after з, с, ц, дз when the following
consonant is soft (снег → сьнег, свет → сьвет, дзверы → дзьверы) and inside
soft geminates (насенне → насеньне, жыццё → жыцьцё, вяселле → вясельле).
Narkamaŭka omits it in exactly those positions, so both directions are
deterministic string rewrites — with a handful of lexical exceptions
(пісьменнік keeps its ь in Narkamaŭka) that live in the lexicon, not here.

All functions are pure ``str -> str`` on lowercase input and are the reference
implementation the YAML rules in ``data/rules/palatalization.yaml`` must agree
with (see ``tests/test_rules.py``).
"""

from __future__ import annotations

from typing import Final

import regex

from belnorm.normalize import CANONICAL_APOSTROPHE

SOFT_VOWELS: Final[str] = "еёіюя"
SOFTENERS: Final[str] = SOFT_VOWELS + "ь"

#: Consonants that soften before a soft vowel and thereby trigger assimilation
#: in the preceding з/с/ц/дз. Velars, hushers, р, д, т never soften.
SOFT_TRIGGERS: Final[frozenset[str]] = frozenset(
    {"в", "м", "п", "б", "л", "н", "с", "з", "ц", "дз"}
)

#: Consonants that take the soft sign under assimilation.
ASSIMILABLE: Final[frozenset[str]] = frozenset({"з", "с", "ц", "дз", "н"})

#: Consonants whose soft geminates are written with ь in Taraškievica.
GEMINABLE: Final[frozenset[str]] = frozenset({"н", "л", "з", "с", "ц", "дз"})

_TRIGGER_ALT: Final[str] = "(?:дз|[вмпблнсзц])"

# --- Narkamaŭka → Taraškievica -------------------------------------------------
ASSIM_PATTERN: Final[str] = rf"(дз|[зсц])(?={_TRIGGER_ALT}[{SOFTENERS}])"
GEMINATE_PATTERN: Final[str] = rf"(дз|[нлзсц])(?=\1[{SOFTENERS}])"
GEMINATE_DZ_PATTERN: Final[str] = rf"д(?=дз[{SOFTENERS}])"  # суддзя → судзьдзя
APOSTROPHE_PATTERN: Final[str] = rf"([зс])[’'ʼ`‘](?=[{SOFT_VOWELS}])"  # з’ява → зьява

_ASSIM_RE: Final[regex.Pattern[str]] = regex.compile(ASSIM_PATTERN)
_GEM_RE: Final[regex.Pattern[str]] = regex.compile(GEMINATE_PATTERN)
_GEM_DZ_RE: Final[regex.Pattern[str]] = regex.compile(GEMINATE_DZ_PATTERN)
_APOS_RE: Final[regex.Pattern[str]] = regex.compile(APOSTROPHE_PATTERN)

# --- Taraškievica → Narkamaŭka -------------------------------------------------
UNASSIM_PATTERN: Final[str] = rf"(дз|[зсц])ь(?={_TRIGGER_ALT}[{SOFTENERS}])"
UNGEMINATE_PATTERN: Final[str] = rf"(дз|[нлзсц])ь(?=\1[{SOFTENERS}])"
UNGEMINATE_DZ_PATTERN: Final[str] = rf"дзь(?=дз[{SOFTENERS}])"
UNAPOSTROPHE_PATTERN: Final[str] = rf"([зс])ь(?=[{SOFT_VOWELS}])"

_UNASSIM_RE: Final[regex.Pattern[str]] = regex.compile(UNASSIM_PATTERN)
_UNGEM_RE: Final[regex.Pattern[str]] = regex.compile(UNGEMINATE_PATTERN)
_UNGEM_DZ_RE: Final[regex.Pattern[str]] = regex.compile(UNGEMINATE_DZ_PATTERN)
_UNAPOS_RE: Final[regex.Pattern[str]] = regex.compile(UNAPOSTROPHE_PATTERN)

_MAX_PASSES: Final[int] = 8


def _fixpoint(word: str, *steps: tuple[regex.Pattern[str], str]) -> str:
    """Apply ``steps`` repeatedly until nothing changes (softness chains leftward)."""
    for _ in range(_MAX_PASSES):
        before = word
        for pattern, repl in steps:
            word = pattern.sub(repl, word)
        if word == before:
            return word
    return word


def mark_assimilative_softness(word: str) -> str:
    """снег → сьнег, свіння → сьвіньня, з’ява → зьява, суддзя → судзьдзя."""
    return _fixpoint(
        word,
        (_APOS_RE, r"\1ь"),
        (_GEM_DZ_RE, "дзь"),
        (_GEM_RE, r"\1ь"),
        (_ASSIM_RE, r"\1ь"),
    )


def unmark_assimilative_softness(word: str) -> str:
    """сьнег → снег, сьвіньня → свіння, зьява → з’ява, судзьдзя → суддзя."""
    # Un-assimilate before un-geminating: dropping the ь of a geminate first
    # would hide the soft trigger that licenses the ь to its left (зьльлю).
    word = _fixpoint(
        word,
        (_UNGEM_DZ_RE, "д"),
        (_UNASSIM_RE, r"\1"),
        (_UNGEM_RE, r"\1"),
    )
    return _UNAPOS_RE.sub(rf"\1{CANONICAL_APOSTROPHE}", word)


def is_palatalizing_context(word: str, i: int) -> bool:
    """Is the consonant at ``word[i]`` followed by a soft consonant?

    True exactly when Taraškievica would write ь after it (given it is an
    assimilable consonant). Handles the дз digraph at ``i`` and at ``i+1``.
    """
    if i < 0 or i >= len(word):
        return False
    here = word[i : i + 2] if word[i : i + 2] == "дз" else word[i]
    if here not in ASSIMILABLE:
        return False
    j = i + len(here)
    nxt = word[j : j + 2] if word[j : j + 2] == "дз" else word[j : j + 1]
    if not nxt:
        return False
    after = word[j + len(nxt) : j + len(nxt) + 1]
    if here == "н":
        return nxt == "н" and after in set(SOFTENERS)
    return nxt in SOFT_TRIGGERS and after in set(SOFTENERS)
