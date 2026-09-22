"""Lexical substitutions whose target depends on grammatical case.

A Narkamaŭka form can be several cases at once while its Taraškievica
substitute distinguishes them: *Германіі* is genitive, dative and locative, but
*Нямеччына* has genitive *Нямеччыны* and dative/locative *Нямеччыне*. The case
is read from the preposition right before the word:

- dative/locative prepositions (у, ў, ва, на, аб, пры, па, к, ка, дзякуючы,
  насустрач, насуперак) select the dative/locative target;
- anything else — a genitive preposition (да, з, ад, для, каля, без …), another
  word, or nothing — selects the genitive target.

The default is a known limitation: a bare dative after a verb (*дапамагаць
Германіі*) gets the genitive form. Source file: ``data/lexicon/case/*.tsv``,
three columns ``narkamauka<TAB>genitive<TAB>dative_locative``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from pravapis.normalize import sanitize

CASE_RULE_ID: Final[str] = "lex.case_context"

#: Which prepositions select the dative/locative column is an inventory, not a rule,
#: so it lives in ``data/morphology/function_words.tsv`` with the other function words.
#: Passed in rather than imported, so a CaseForms built for a test can carry its own.


class CaseForms:
    def __init__(
        self,
        table: dict[str, tuple[str, str]],
        dative_locative: frozenset[str] = frozenset(),
    ):
        self._table = table
        self._dative_locative = dative_locative

    @classmethod
    def load(cls, path: Path, dative_locative: frozenset[str] = frozenset()) -> CaseForms:
        files = sorted(path.glob("*.tsv")) if path.is_dir() else [path]
        table: dict[str, tuple[str, str]] = {}
        for f in files:
            for line_no, raw in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if not raw.strip() or raw.lstrip().startswith("#"):
                    continue
                cols = [sanitize(c.strip()).lower() for c in raw.split("\t")]
                if len(cols) != 3:
                    raise ValueError(f"{f}:{line_no}: expected 3 tab-separated columns")
                table.setdefault(cols[0], (cols[1], cols[2]))
        return cls(table, dative_locative)

    @classmethod
    def empty(cls) -> CaseForms:
        return cls({})

    def __contains__(self, word: str) -> bool:
        return word.lower() in self._table

    def __len__(self) -> int:
        return len(self._table)

    def choose(self, word: str, previous: str | None) -> tuple[str, str] | None:
        """(lowercase target, reason) for ``word`` after ``previous``, or None if not listed."""
        entry = self._table.get(word.lower())
        if entry is None:
            return None
        genitive, dative_locative = entry
        prev = (previous or "").lower()
        if prev in self._dative_locative:
            return dative_locative, f"after «{prev}»: dative/locative"
        return genitive, "genitive (default: no dative/locative preposition before it)"
