"""Build the static lexicon from TSV sources.

Source format (``data/lexicon/*.tsv``)::

    # comment lines start with '#'
    narkamauka<TAB>taraskievica
    narkamauka<TAB>taraskievica<TAB>n2t    # one-way entry

An optional third column restricts an entry to one direction: ``n2t`` builds
only the Narkamaŭka → Taraškievica key, ``t2n`` only the reverse. Use it when
the target form is also an unrelated word on its own side (літр → літар is
right, but Taraškievica *літар* is also the genitive plural of *літара*).

Entries are lowercased on build; capitalisation is re-applied at lookup time.
The first entry for a key wins, so put preferred variants first.

The compiled container records a SHA-256 of its TSV sources, so a loader can
refuse a file built from sources that have since changed (see
``Lexicon.load(..., sources=...)``).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import marisa_trie
import regex

from pravapis.normalize import sanitize
from pravapis.tokenize import BELARUSIAN_LETTERS, tokenize
from pravapis.types import Orthography, TokenKind

#: v2 container: magic, 32-byte SHA-256 of the sources, u32 forward length, forward, reverse.
LEXICON_MAGIC: Final[bytes] = b"PRAVAPIS2"
#: Containers written before the project was renamed, or before source hashing.
_OLD_MAGICS: Final[tuple[bytes, ...]] = (b"PRAVAPIS1", b"BELNORM2", b"BELNORM1")
_DIGEST_LEN: Final[int] = 32


class StaleLexiconError(ValueError):
    """A compiled lexicon does not match its TSV sources (or predates source hashing)."""


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


_ONE_WAY: Final[dict[str, Orthography]] = {
    "n2t": Orthography.TARASKIEVICA,
    "t2n": Orthography.NARKAMAUKA,
}


def read_tsv_pairs(
    path: Path, *, usable_for: Orthography | None = None
) -> Iterator[tuple[str, str]]:
    """Yield (narkamauka, taraskievica) pairs; blank lines and ``#`` comments skipped.

    With ``usable_for`` (the target orthography), one-way entries for the other
    direction are dropped.
    """
    with path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            line = raw.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                raise ValueError(f"{path}:{line_no}: expected two tab-separated columns")
            flag = parts[2].strip() if len(parts) > 2 else ""
            if flag and flag not in _ONE_WAY:
                raise ValueError(f"{path}:{line_no}: third column must be n2t or t2n, got {flag!r}")
            if usable_for is not None and flag and _ONE_WAY[flag] is not usable_for:
                continue
            yield sanitize(parts[0].strip()), sanitize(parts[1].strip())


def read_tsv_dir(path: Path, *, usable_for: Orthography | None = None) -> Iterator[tuple[str, str]]:
    for tsv in sorted(path.glob("*.tsv")):
        yield from read_tsv_pairs(tsv, usable_for=usable_for)


def read_sources(path: Path, usable_for: Orthography | None = None) -> list[tuple[str, str]]:
    """A TSV file or a directory of them."""
    if path.is_dir():
        return list(read_tsv_dir(path, usable_for=usable_for))
    return list(read_tsv_pairs(path, usable_for=usable_for))


def build_from_sources(path: Path) -> tuple[marisa_trie.BytesTrie, marisa_trie.BytesTrie]:
    """Forward and reverse tries, honouring one-way entries."""
    fwd = build_trie(read_sources(path, Orthography.TARASKIEVICA))
    rev = build_trie((t, s) for s, t in read_sources(path, Orthography.NARKAMAUKA))
    return fwd, rev


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


def sources_digest(path: Path) -> bytes:
    """SHA-256 over the TSV sources: a file, or every ``*.tsv`` in a directory.

    File names and contents both count. Line endings are normalised first, so a
    CRLF checkout on Windows and an LF checkout on Linux hash the same.
    """
    files = sorted(path.glob("*.tsv")) if path.is_dir() else [path]
    h = hashlib.sha256()
    for f in files:
        h.update(f.name.encode("utf-8") + b"\0")
        h.update(f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.digest()


def save_lexicon(
    fwd: marisa_trie.BytesTrie,
    rev: marisa_trie.BytesTrie,
    path: Path,
    *,
    source_digest: bytes,
) -> None:
    """Write both tries and the sources' digest into one container file."""
    if len(source_digest) != _DIGEST_LEN:
        raise ValueError("source_digest must be a 32-byte SHA-256 digest")
    fwd_bytes = fwd.tobytes()
    rev_bytes = rev.tobytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        fh.write(LEXICON_MAGIC)
        fh.write(source_digest)
        fh.write(len(fwd_bytes).to_bytes(4, "little"))
        fh.write(fwd_bytes)
        fh.write(rev_bytes)


def write_data_hash_marker(out: Path, data_root: Path | None = None) -> Path:
    """Write an empty ``<out-stem>-<data_hash>.built`` marker next to ``out``.

    Lets a build (or a test) read the data hash straight off a filename instead of
    recomputing it, and cross-check it against ``pravapis.dataversion.compute_data_hash``
    for the same data tree — the single computation GET /v1/version also reports.
    Removes any stale marker for the same ``out`` stem first, so exactly one exists
    per build.
    """
    from pravapis.dataversion import compute_data_hash

    digest = compute_data_hash(data_root)
    for stale in out.parent.glob(f"{out.stem}-*.built"):
        stale.unlink()
    marker = out.parent / f"{out.stem}-{digest}.built"
    marker.touch()
    return marker


def load_lexicon_file(
    path: Path,
) -> tuple[marisa_trie.BytesTrie, marisa_trie.BytesTrie, bytes]:
    """Forward trie, reverse trie, and the digest of the sources the file was built from."""
    data = path.read_bytes()
    if data.startswith(_OLD_MAGICS):
        raise StaleLexiconError(
            f"{path}: built by an older pravapis (or by belnorm, before the rename); "
            "rebuild with `pravapis build-lexicon`"
        )
    if not data.startswith(LEXICON_MAGIC):
        raise ValueError(f"{path}: not a pravapis lexicon file")
    offset = len(LEXICON_MAGIC)
    digest = data[offset : offset + _DIGEST_LEN]
    offset += _DIGEST_LEN
    fwd_len = int.from_bytes(data[offset : offset + 4], "little")
    offset += 4
    fwd = marisa_trie.BytesTrie()
    fwd.frombytes(data[offset : offset + fwd_len])
    rev = marisa_trie.BytesTrie()
    rev.frombytes(data[offset + fwd_len :])
    return fwd, rev, digest
