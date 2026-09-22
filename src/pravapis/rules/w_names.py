"""The W-name inventory: words whose initial Ў is English *W*, not Збор 2005 §18.

§18 turns an unstressed initial У into Ў after a vowel, and the reverse direction undoes
it. Belarusian also writes Ў at the start of a name to render English *W* — *Ўіл*,
*Ўотэрз*, *Ўэйлз* — and Narkamaŭka keeps that Ў. After a vowel the two are
indistinguishable (*школу Ўайлд* could be either), so `initial_w_to_u` has to know which
words are names.

That is a fact about particular words, not a pattern in them, which makes it **data**.
It lives in ``data/lexicon/w_names.tsv``, under the data version like every other table
the converter reads, and is mined by ``scripts/mine_w_names.py`` from Wikidata items
whose English label begins with W and whose be-tarask label begins with Ў.

The list is open-ended by nature. An unlisted W-name that follows a vowel will come back
from T → N with У — a real limit of the rule, recorded in ``data/NORMS.md`` rather than
hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pravapis.normalize import sanitize

#: Where a row came from. ``hand`` rows were read off an attested sentence in
#: ``data/eval/tarask/gold_t2n.tsv``; ``wikidata`` rows from an aligned label pair.
W_NAME_PROVENANCES: Final[frozenset[str]] = frozenset({"hand", "wikidata"})

#: Relative to the data directory.
W_NAMES_FILE: Final[str] = "names/w_names.tsv"

#: The schema this file is written against, declared in its own ``#!schema`` line.
SCHEMA_ID: Final[str] = "tag:pravapis,2026:schema:w_names:1"

#: Column order, declared in the file's ``#!columns`` line.
DECLARED_COLUMNS: Final[tuple[str, ...]] = ("stem", "provenance", "evidence")


class WNameError(ValueError):
    """The W-name inventory is malformed."""


@dataclass(frozen=True, slots=True)
class WNameEntry:
    """One stem whose initial Ў must survive T → N."""

    stem: str
    provenance: str
    evidence: str


def read_w_names(path: Path) -> list[WNameEntry]:
    """``stem<TAB>provenance<TAB>evidence`` rows; blank lines and ``#`` comments skipped."""
    rows: list[WNameEntry] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            raise WNameError(f"{path}:{number}: expected 3 columns, got {len(parts)}")
        stem = sanitize(parts[0].strip()).lower()
        provenance = parts[1].strip()
        if not stem.startswith("ў"):
            raise WNameError(f"{path}:{number}: {stem!r} does not begin with ў")
        if provenance not in W_NAME_PROVENANCES:
            raise WNameError(
                f"{path}:{number}: provenance {provenance!r} is not one of "
                f"{sorted(W_NAME_PROVENANCES)}"
            )
        rows.append(WNameEntry(stem=stem, provenance=provenance, evidence=parts[2].strip()))
    return rows


@dataclass(frozen=True, slots=True)
class WNames:
    """Prefix membership over the inventory.

    A tuple, matched with :meth:`str.startswith`, for the same reason the hand-written
    constant it replaces was one: the list is short, the test is a prefix test, and
    ``startswith`` takes the whole tuple in one call.
    """

    stems: tuple[str, ...] = ()

    @classmethod
    def load(cls, data_dir: Path) -> WNames:
        path = data_dir / W_NAMES_FILE
        if not path.is_file():
            return cls(())
        return cls(tuple(sorted({row.stem for row in read_w_names(path)})))

    @classmethod
    def empty(cls) -> WNames:
        return cls(())

    def __contains__(self, word: str) -> bool:
        return bool(self.stems) and word.lower().startswith(self.stems)

    def __len__(self) -> int:
        return len(self.stems)
