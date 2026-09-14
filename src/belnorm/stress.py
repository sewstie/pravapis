"""First-syllable stress lookup from GrammarDB stress marks.

Jakanne in Taraškievica (не → ня, без → бяз) depends on whether the next word
is stressed on its first syllable. ``data/stress/`` holds the forms GrammarDB
stresses there unambiguously (built by ``scripts/build_stress_table.py`` from a
verified release). A word not in the table — unknown, homograph, or stressed
elsewhere — is reported as not first-stressed, so the particle stays as it is.

Data: GrammarDB (Aleś Bułojčyk, Uładzimir Koščanka), CC BY-SA 4.0.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Final

import marisa_trie

VOWELS: Final[frozenset[str]] = frozenset("аеёіоуыэюя")

COMMON_FILE: Final[str] = "first_stressed.marisa"
PROPER_FILE: Final[str] = "proper_first_stressed.marisa"


class StressTable:
    def __init__(self, common: marisa_trie.Trie, proper: marisa_trie.Trie):
        self._common = common
        self._proper = proper

    @classmethod
    def load(cls, directory: Path) -> StressTable:
        common = marisa_trie.Trie()
        common.load(str(directory / COMMON_FILE))
        proper = marisa_trie.Trie()
        proper_path = directory / PROPER_FILE
        if proper_path.is_file():
            proper.load(str(proper_path))
        return cls(common, proper)

    @classmethod
    def from_words(cls, common: Iterable[str], proper: Iterable[str] = ()) -> StressTable:
        return cls(marisa_trie.Trie(list(common)), marisa_trie.Trie(list(proper)))

    def __len__(self) -> int:
        return len(self._common) + len(self._proper)

    def is_first_stressed(self, word: str) -> bool:
        """Does GrammarDB stress ``word`` on its first syllable, unambiguously?

        Lowercase forms are checked against common words, then — for a
        capitalised word — against proper names. For a hyphenated compound the
        first part decides.
        """
        if not word:
            return False
        lw = word.lower()
        if lw in self._common:
            return True
        if word[:1].isupper() and word in self._proper:
            return True
        if "-" in word:
            head = word.split("-", 1)[0]
            return bool(head) and self.is_first_stressed(head)
        return False
