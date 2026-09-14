"""Read-only lexicon backed by two ``marisa_trie.BytesTrie`` instances.

One trie per direction. Keys are lowercase; ``lookup_ci`` casefolds the query
and re-applies the query's capitalisation pattern to the result, so
``Мінск`` → ``Менск`` and ``МІНСК`` → ``МЕНСК`` without storing either.

``Lexicon.load`` accepts either a compiled ``.marisa`` container (built by
``belnorm build-lexicon``) or a directory / single ``.tsv`` file, in which
case the tries are built in memory. The latter is what makes the dev loop
"edit TSV, rerun tests" and is exactly what phase 1 needed.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import marisa_trie

from belnorm.casing import recase
from belnorm.lexicon.builder import (
    build_both,
    load_lexicon_file,
    read_tsv_dir,
    read_tsv_pairs,
)
from belnorm.types import Orthography


class Lexicon:
    def __init__(self, n2t: marisa_trie.BytesTrie, t2n: marisa_trie.BytesTrie):
        self._n2t = n2t
        self._t2n = t2n

    # --- construction ---------------------------------------------------------
    @classmethod
    def load(cls, path: Path) -> Lexicon:
        if path.is_dir():
            return cls.from_pairs(read_tsv_dir(path))
        if path.suffix == ".tsv":
            return cls.from_pairs(read_tsv_pairs(path))
        return cls(*load_lexicon_file(path))

    @classmethod
    def from_pairs(cls, pairs: Iterable[tuple[str, str]]) -> Lexicon:
        return cls(*build_both(pairs))

    @classmethod
    def empty(cls) -> Lexicon:
        return cls(marisa_trie.BytesTrie(), marisa_trie.BytesTrie())

    # --- queries --------------------------------------------------------------
    def _trie(self, direction: Orthography) -> marisa_trie.BytesTrie:
        return self._n2t if direction is Orthography.TARASKIEVICA else self._t2n

    def lookup(self, word: str, direction: Orthography) -> str | None:
        """Exact-key lookup (keys are lowercase). ``direction`` is the target orthography."""
        values = self._trie(direction).get(word)
        if not values:
            return None
        first: bytes = values[0]
        return first.decode("utf-8")

    def lookup_ci(self, word: str, direction: Orthography) -> str | None:
        hit = self.lookup(word.lower(), direction)
        return None if hit is None else recase(word, hit)

    def is_identity(self, word: str) -> bool:
        """Is ``word`` explicitly listed as spelled the same in both orthographies?"""
        w = word.lower()
        return (
            self.lookup(w, Orthography.TARASKIEVICA) == w
            or self.lookup(w, Orthography.NARKAMAUKA) == w
        )

    def prefix_search(self, prefix: str, limit: int = 20) -> list[str]:
        prefix = prefix.lower()
        keys: set[str] = set(self._n2t.keys(prefix)) | set(self._t2n.keys(prefix))
        return sorted(keys)[:limit]

    def __contains__(self, word: str) -> bool:
        w = word.lower()
        return w in self._n2t or w in self._t2n

    def __len__(self) -> int:
        return len(self._n2t)

    def __repr__(self) -> str:
        return f"Lexicon(n2t={len(self._n2t)}, t2n={len(self._t2n)})"
