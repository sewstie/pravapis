"""The function-word inventories, read from data rather than written in Python.

Six closed lists decide what the converter does with particular words: which proclitics
take jakanne (не → ня), which prepositions take assimilative softness (зь вераю), which
words never count as a stressed first syllable, which stems §18's stress exception
covers, and which prepositions select the dative/locative column of the case table.

They are **inventories, not patterns**. A rule file can show a port how softness works;
nothing in it can show a port that *цераз* belongs on the softening list and *каля* does
not. Constants in Python are invisible to every implementation but this one, so the
lists live in ``data/morphology/function_words.tsv`` under the data version, and this
module reads them.

Loaded once and memoised on the data directory: these are read on the hot path, and
re-reading a TSV per token would be the slowest thing in the cascade.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

from pravapis.normalize import sanitize

#: Relative to the data directory.
FUNCTION_WORDS_FILE: Final[str] = "morphology/function_words.tsv"

#: Declared in the file's own ``#!schema`` line.
SCHEMA_ID: Final[str] = "tag:pravapis,2026:schema:function_words:1"

#: Declared in the file's ``#!columns`` line.
DECLARED_COLUMNS: Final[tuple[str, ...]] = ("form", "role", "target", "citation")

#: Roles a row may take. Each is documented in the file's own header.
ROLES: Final[frozenset[str]] = frozenset(
    {
        "particle_n2t",
        "particle_t2n",
        "softening_preposition",
        "clitic",
        "stressed_initial_u",
        "dative_locative_preposition",
    }
)

#: Roles whose rows must carry a real target rather than ``-``.
_NEEDS_TARGET: Final[frozenset[str]] = frozenset({"particle_n2t", "particle_t2n"})


class FunctionWordError(ValueError):
    """The function-word inventory is malformed."""


@dataclass(frozen=True, slots=True)
class FunctionWord:
    form: str
    role: str
    target: str | None
    citation: str


def read_function_words(path: Path) -> list[FunctionWord]:
    """``form<TAB>role<TAB>target<TAB>citation`` rows; blanks and ``#`` comments skipped."""
    rows: list[FunctionWord] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            raise FunctionWordError(f"{path}:{number}: expected 4 columns, got {len(parts)}")
        form = sanitize(parts[0].strip()).lower()
        role = parts[1].strip()
        raw_target = parts[2].strip()
        if role not in ROLES:
            raise FunctionWordError(f"{path}:{number}: role {role!r} is not one of {sorted(ROLES)}")
        target = None if raw_target == "-" else sanitize(raw_target).lower()
        if role in _NEEDS_TARGET and target is None:
            raise FunctionWordError(
                f"{path}:{number}: role {role!r} needs a target, not '-' — the row says a "
                "word changes but not into what"
            )
        rows.append(FunctionWord(form=form, role=role, target=target, citation=parts[3].strip()))
    return rows


@dataclass(frozen=True, slots=True)
class FunctionWords:
    """The six inventories, in the shapes the call sites actually want."""

    particles_n2t: dict[str, str]
    particles_t2n: dict[str, str]
    softening_prepositions: frozenset[str]
    clitics: frozenset[str]
    stressed_initial_u: tuple[str, ...]
    dative_locative_prepositions: frozenset[str]

    @classmethod
    def from_rows(cls, rows: list[FunctionWord]) -> FunctionWords:
        n2t: dict[str, str] = {}
        t2n: dict[str, str] = {}
        softening: set[str] = set()
        clitics: set[str] = set()
        stressed: list[str] = []
        dative: set[str] = set()
        for row in rows:
            match row.role:
                case "particle_n2t":
                    assert row.target is not None
                    n2t[row.form] = row.target
                case "particle_t2n":
                    assert row.target is not None
                    t2n[row.form] = row.target
                case "softening_preposition":
                    softening.add(row.form)
                case "clitic":
                    clitics.add(row.form)
                case "stressed_initial_u":
                    stressed.append(row.form)
                case "dative_locative_preposition":
                    dative.add(row.form)
        return cls(
            particles_n2t=n2t,
            particles_t2n=t2n,
            softening_prepositions=frozenset(softening),
            clitics=frozenset(clitics),
            # `str.startswith` takes a tuple, and a longer stem must not be shadowed by
            # a shorter one that happens to precede it, so the order is fixed here.
            stressed_initial_u=tuple(sorted(stressed)),
            dative_locative_prepositions=frozenset(dative),
        )

    @classmethod
    def load(cls, data_dir: Path) -> FunctionWords:
        """Read the inventories for ``data_dir``, falling back to the shipped ones.

        Unlike the stress table or the case file, there is no ``Config`` field that can
        say "this deployment has no function words" — every conversion needs them. So a
        data directory that does not carry the file (a hand-built ``Config`` pointing at
        a bare lexicon, say) gets the inventories this build ships rather than an empty
        set, which would silently stop converting не → ня and зь.
        """
        local = data_dir / FUNCTION_WORDS_FILE
        if local.is_file():
            return _load(data_dir.resolve())
        from pravapis.config import find_data_dir

        shipped = find_data_dir()
        if (shipped / FUNCTION_WORDS_FILE).is_file():
            return _load(shipped.resolve())
        raise FunctionWordError(
            f"{local} is missing, and so is {shipped / FUNCTION_WORDS_FILE}. The file "
            "holds the particle, clitic and preposition inventories the converter "
            "needs; without it не/ня, зь and the §18 stress exception stop working."
        )

    @classmethod
    def empty(cls) -> FunctionWords:
        return cls({}, {}, frozenset(), frozenset(), (), frozenset())


@lru_cache(maxsize=4)
def _load(data_dir: Path) -> FunctionWords:
    return FunctionWords.from_rows(read_function_words(data_dir / FUNCTION_WORDS_FILE))


def default_function_words() -> FunctionWords:
    """The inventories from the data directory this build resolves."""
    from pravapis.config import find_data_dir

    return FunctionWords.load(find_data_dir())
