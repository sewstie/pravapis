"""Stem-level etymology index: which stems are Western borrowings and which are native.

The loanword alternations (soft *l*, і → ы, е → э) are fully regular *given* that
a word is a borrowing — Збор 2005 §11б states the э rule as a plain phonological
condition. What is not recoverable from the surface form is the etymology itself:
native ``лапа`` and borrowed ``лямпа`` share every visible property.

This index supplies exactly that missing fact, one row per stem, so the rules can
stay general and the data can grow without touching Python.

Source format (``data/lexicon/stems.tsv``)::

    # stem <TAB> class <TAB> alternations <TAB> source <TAB> provenance [<TAB> target]
    план      loan    l       §55.1       cited
    версі     loan    e       §11б        cited
    -логі     loan    l       §55.1       cited
    класц     native  -       -           cited
    каланіял  loan    -       §55.1       cited      калёніял

``class`` is ``loan`` or ``native``. ``alternations`` is a comma-separated subset
of :data:`ALTERNATIONS`, or ``-``. A leading ``-`` on the stem marks it unanchored
(it may match anywhere in the word, not only at the start): ``-логі`` is how
``біялогія`` is reached without also matching ``падлогі``.

**Longest match wins**, which is how false friends are handled: ``класц`` (native)
beats ``клас`` (loan) on the word ``класці``, with no lookahead in sight. Adding a
false friend is a one-line edit rather than a regex someone has to get right.

The optional sixth column is an escape hatch for stems whose Taraškievica form the
regular alternations cannot derive — ``каланіял → калёніял`` restores an
etymological *о* that Narkamaŭka's akanne wrote as *а*, which no rule conditioned
on the Narkamaŭka spelling can know. Prefer ``alternations``; reach for ``target``
only when the alternation genuinely does not exist.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

import marisa_trie
import regex

from pravapis.normalize import sanitize


class WordClass(StrEnum):
    """Etymology of a stem, as far as the loanword rules care."""

    LOAN = "loan"
    NATIVE = "native"


class Provenance(StrEnum):
    """How an entry got here. ``UNCERTAIN`` rows are parsed, counted and never applied."""

    CITED = "cited"  # a § of the codification, or a named dictionary page
    REVIEWED = "reviewed"  # read and accepted by a human against a cited class rule
    DERIVED = "derived"  # produced by scripts/mine_loan_stems.py, not yet reviewed
    UNCERTAIN = "uncertain"


#: Provenance tiers that are actually applied at conversion time.
APPLIED: Final[frozenset[Provenance]] = frozenset(
    {Provenance.CITED, Provenance.REVIEWED, Provenance.DERIVED}
)

#: Alternation codes a stem may license.
ALTERNATIONS: Final[frozenset[str]] = frozenset({"l", "i", "e", "g", "eu"})

_NO_VALUE: Final[frozenset[str]] = frozenset({"", "-", "?"})


@dataclass(frozen=True, slots=True)
class StemEntry:
    stem: str
    cls: WordClass
    alternations: frozenset[str]
    source: str
    provenance: Provenance
    anchored: bool = True
    target: str | None = None
    #: alternations written ``code:n2t`` — derivable forwards, ambiguous backwards.
    #: Taraškievica *салён-* is both the loan (salon) and the native adjective
    #: (salty), so салон → салён is safe while салёны → салоны is not.
    forward_only: frozenset[str] = frozenset()

    @property
    def applied(self) -> bool:
        return self.provenance in APPLIED


@dataclass(frozen=True, slots=True)
class StemMatch:
    """Where a known stem was found in a word, and what it licenses."""

    stem: str
    cls: WordClass
    alternations: frozenset[str]
    start: int
    end: int
    target: str | None = None
    #: length of the word this match was resolved against. Etymology is resolved once,
    #: from the word as it arrived, so a later rule that changes the word's *length*
    #: invalidates these indices. A change at the same length (класі → клясі, one
    #: alternation feeding the next) does not.
    word_len: int = -1

    def spans(self, word: str) -> bool:
        """Are ``start``/``end`` still pointing at the right letters of ``word``?"""
        return self.word_len < 0 or len(word) == self.word_len

    def allows(self, alternation: str) -> bool:
        return self.cls is WordClass.LOAN and alternation in self.alternations


class StemError(ValueError):
    """A stems file is malformed."""


def read_stems(path: Path) -> Iterator[StemEntry]:
    """Yield entries from a TSV file; blank lines and ``#`` comments skipped."""
    with path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            line = raw.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = [p.strip() for p in line.split("\t")]
            if len(parts) < 5:
                raise StemError(
                    f"{path}:{line_no}: expected at least 5 tab-separated columns, got {len(parts)}"
                )
            stem_raw, cls_raw, alt_raw, source, prov_raw = parts[:5]
            target = parts[5] if len(parts) > 5 and parts[5] not in _NO_VALUE else None

            anchored = not stem_raw.startswith("-")
            stem = sanitize(stem_raw.lstrip("-")).lower()
            if not stem:
                raise StemError(f"{path}:{line_no}: empty stem")
            try:
                cls = WordClass(cls_raw)
            except ValueError as exc:
                raise StemError(
                    f"{path}:{line_no}: class must be one of "
                    f"{sorted(c.value for c in WordClass)}, got {cls_raw!r}"
                ) from exc
            try:
                provenance = Provenance(prov_raw)
            except ValueError as exc:
                raise StemError(
                    f"{path}:{line_no}: provenance must be one of "
                    f"{sorted(p.value for p in Provenance)}, got {prov_raw!r}"
                ) from exc

            alternations: frozenset[str] = frozenset()
            forward_only: frozenset[str] = frozenset()
            if alt_raw not in _NO_VALUE:
                codes: set[str] = set()
                one_way: set[str] = set()
                for token in (a.strip() for a in alt_raw.split(",")):
                    if not token:
                        continue
                    code, _, restriction = token.partition(":")
                    if restriction and restriction not in {"n2t", "t2n"}:
                        raise StemError(
                            f"{path}:{line_no}: alternation restriction must be n2t or t2n, "
                            f"got {restriction!r}"
                        )
                    codes.add(code)
                    if restriction == "n2t":
                        one_way.add(code)
                alternations = frozenset(codes)
                forward_only = frozenset(one_way)
                unknown = alternations - ALTERNATIONS
                if unknown:
                    raise StemError(
                        f"{path}:{line_no}: unknown alternation(s) {sorted(unknown)}; "
                        f"known: {sorted(ALTERNATIONS)}"
                    )
            if cls is WordClass.NATIVE and (alternations or target):
                raise StemError(
                    f"{path}:{line_no}: a native stem licenses nothing; "
                    "leave alternations and target empty"
                )
            yield StemEntry(
                stem=stem,
                cls=cls,
                alternations=alternations,
                source=source if source not in _NO_VALUE else "",
                provenance=provenance,
                anchored=anchored,
                target=sanitize(target).lower() if target else None,
                forward_only=forward_only,
            )


def read_stem_sources(path: Path) -> list[StemEntry]:
    """A TSV file, or every ``*.tsv`` in a directory."""
    files = sorted(path.glob("*.tsv")) if path.is_dir() else [path]
    out: list[StemEntry] = []
    for f in files:
        out.extend(read_stems(f))
    return out


def validate_stems(entries: Iterable[StemEntry]) -> list[str]:
    """Human-readable problems: duplicates, uncitable claims, rules that can never fire.

    Only *loan* stems need a citation. A native stem claims nothing about the
    codification — it says the word is ordinary Belarusian vocabulary, which is what
    makes the loanword rules leave it alone.
    """
    problems: list[str] = []
    seen: dict[tuple[str, bool], StemEntry] = {}
    for e in entries:
        key = (e.stem, e.anchored)
        if key in seen:
            problems.append(f"duplicate stem {e.stem!r} (also {seen[key].cls.value})")
        seen[key] = e
        if e.cls is WordClass.LOAN and e.provenance is Provenance.CITED and not e.source:
            problems.append(f"loan stem {e.stem!r} is marked cited but has no source")
        if e.cls is WordClass.LOAN and e.provenance in APPLIED and not (e.alternations or e.target):
            problems.append(f"loan stem {e.stem!r} would never fire: no alternations and no target")
    return problems


class StemIndex:
    """Longest-match lookup over the stem inventory.

    Anchored stems live in a ``marisa_trie.Trie``: ``prefixes(word)`` returns every
    key that prefixes the word in a single pass, so this stays O(len(word)) no matter
    how large the inventory grows. Unanchored stems are far fewer and go through one
    compiled alternation, longest alternative first.
    """

    def __init__(self, entries: Iterable[StemEntry]):
        applied = [e for e in entries if e.applied]
        self._by_key: dict[tuple[str, bool], StemEntry] = {(e.stem, e.anchored): e for e in applied}
        anchored = [e.stem for e in applied if e.anchored]
        self._trie = marisa_trie.Trie(anchored)
        unanchored = sorted((e.stem for e in applied if not e.anchored), key=len, reverse=True)
        self._unanchored: regex.Pattern[str] | None = (
            regex.compile("|".join(regex.escape(s) for s in unanchored)) if unanchored else None
        )

    @classmethod
    def load(cls, path: Path) -> StemIndex:
        return cls(read_stem_sources(path))

    @classmethod
    def empty(cls) -> StemIndex:
        return cls(())

    def match(self, word: str) -> StemMatch | None:
        """The longest known stem in ``word``; anchored wins ties."""
        w = word.lower()
        best: StemMatch | None = None
        for stem in self._trie.prefixes(w):
            entry = self._by_key[(stem, True)]
            if best is None or len(stem) > best.end - best.start:
                best = StemMatch(stem, entry.cls, entry.alternations, 0, len(stem), entry.target)
        if self._unanchored is not None:
            m = self._unanchored.search(w)
            if m is not None:
                entry = self._by_key[(m.group(0), False)]
                span = m.end() - m.start()
                if best is None or span > best.end - best.start:
                    best = StemMatch(
                        m.group(0),
                        entry.cls,
                        entry.alternations,
                        m.start(),
                        m.end(),
                        entry.target,
                        len(w),
                    )
        return best

    def __len__(self) -> int:
        return len(self._by_key)

    def __repr__(self) -> str:
        loans = sum(1 for e in self._by_key.values() if e.cls is WordClass.LOAN)
        return f"StemIndex({loans} loan, {len(self._by_key) - loans} native)"
