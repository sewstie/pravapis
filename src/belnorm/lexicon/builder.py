"""Build the static lexicon from TSV sources.

Source format (``data/lexicon/*.tsv``)::

    # comment lines start with '#'
    narkamauka<TAB>taraskievica

Entries are lowercased on build; capitalisation is re-applied at lookup time.
The first entry for a key wins, so put preferred variants first.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import marisa_trie
import regex

from belnorm.normalize import sanitize
from belnorm.tokenize import BELARUSIAN_LETTERS, tokenize
from belnorm.types import TokenKind

LEXICON_MAGIC: Final[bytes] = b"BELNORM1"

_ALLOWED: Final[frozenset[str]] = BELARUSIAN_LETTERS | frozenset("’-")
_WS: Final[regex.Pattern[str]] = regex.compile(r"\s")


@dataclass(frozen=True, slots=True)
class ValidationError:
    index: int  # 0-based position in the input sequence
    source: str
    target: str
    message: str
    severity: str = "error"  # "error" | "warning"

    def __str__(self) -> str:
        return f"[{self.severity}] #{self.index} {self.source!r} -> {self.target!r}: {self.message}"


def read_tsv_pairs(path: Path) -> Iterator[tuple[str, str]]:
    """Yield (narkamauka, taraskievica) pairs; blank lines and ``#`` comments skipped."""
    with path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            line = raw.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                raise ValueError(f"{path}:{line_no}: expected two tab-separated columns")
            yield sanitize(parts[0].strip()), sanitize(parts[1].strip())


def read_tsv_dir(path: Path) -> Iterator[tuple[str, str]]:
    for tsv in sorted(path.glob("*.tsv")):
        yield from read_tsv_pairs(tsv)


def align_corpora(a: Path, b: Path) -> Iterator[tuple[str, str]]:
    """Word-align two line-parallel files and yield the pairs that differ.

    Lines whose word counts disagree are skipped: cheap and conservative,
    which is what you want when mining a lexicon from noisy parallel text.
    """
    with a.open(encoding="utf-8") as fa, b.open(encoding="utf-8") as fb:
        for line_a, line_b in zip(fa, fb, strict=False):
            words_a = [t.text for t in tokenize(sanitize(line_a)) if t.kind is TokenKind.WORD]
            words_b = [t.text for t in tokenize(sanitize(line_b)) if t.kind is TokenKind.WORD]
            if len(words_a) != len(words_b):
                continue
            for wa, wb in zip(words_a, words_b, strict=True):
                if wa.lower() != wb.lower():
                    yield wa.lower(), wb.lower()


def validate_entries(pairs: Iterable[tuple[str, str]]) -> list[ValidationError]:
    problems: list[ValidationError] = []
    seen: dict[str, str] = {}
    for i, (src, tgt) in enumerate(pairs):
        if not src or not tgt:
            problems.append(ValidationError(i, src, tgt, "empty side"))
            continue
        for side, word in (("source", src), ("target", tgt)):
            if _WS.search(word):
                problems.append(ValidationError(i, src, tgt, f"{side} contains whitespace"))
            bad = {c for c in word.lower() if c not in _ALLOWED}
            if bad:
                problems.append(
                    ValidationError(
                        i, src, tgt, f"{side} has non-Belarusian characters {sorted(bad)}"
                    )
                )
        key = src.lower()
        if key in seen and seen[key] != tgt.lower():
            problems.append(
                ValidationError(
                    i, src, tgt, f"conflicts with earlier entry -> {seen[key]!r}", "warning"
                )
            )
        seen.setdefault(key, tgt.lower())
    return problems


def build_trie(pairs: Iterable[tuple[str, str]]) -> marisa_trie.BytesTrie:
    """First occurrence of a key wins."""
    table: dict[str, bytes] = {}
    for src, tgt in pairs:
        table.setdefault(src.lower(), tgt.lower().encode("utf-8"))
    return marisa_trie.BytesTrie(table.items())


def build_both(
    pairs: Iterable[tuple[str, str]],
) -> tuple[marisa_trie.BytesTrie, marisa_trie.BytesTrie]:
    materialised = list(pairs)
    fwd = build_trie(materialised)
    rev = build_trie((t, s) for s, t in materialised)
    return fwd, rev


def save_lexicon(fwd: marisa_trie.BytesTrie, rev: marisa_trie.BytesTrie, path: Path) -> None:
    """Write both tries into one container file: magic, u32 length, fwd bytes, rev bytes."""
    fwd_bytes = fwd.tobytes()
    rev_bytes = rev.tobytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        fh.write(LEXICON_MAGIC)
        fh.write(len(fwd_bytes).to_bytes(4, "little"))
        fh.write(fwd_bytes)
        fh.write(rev_bytes)


def load_lexicon_file(path: Path) -> tuple[marisa_trie.BytesTrie, marisa_trie.BytesTrie]:
    data = path.read_bytes()
    if not data.startswith(LEXICON_MAGIC):
        raise ValueError(f"{path}: not a belnorm lexicon file")
    offset = len(LEXICON_MAGIC)
    fwd_len = int.from_bytes(data[offset : offset + 4], "little")
    offset += 4
    fwd = marisa_trie.BytesTrie()
    fwd.frombytes(data[offset : offset + fwd_len])
    rev = marisa_trie.BytesTrie()
    rev.frombytes(data[offset + fwd_len :])
    return fwd, rev
