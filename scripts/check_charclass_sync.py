"""CI guard: the character-class literals in tokenize.py/normalize.py match data/chars/.

    python scripts/check_charclass_sync.py

The Belarusian alphabet, the apostrophe class, and the homoglyph map are shared
primitives: every implementation's tokenizer and sanitizer needs the same three
tables, and ``data/chars/*.tsv`` (NORMATIVE — see ``data/schemas/{alphabet,
apostrophes,homoglyphs}.schema.json``) is where this project writes them down once, so
a JS port reads the same file a human reads instead of reverse-engineering
``src/pravapis/tokenize.py``.

``tokenize.py`` and ``normalize.py`` do **not** read these files at import time —
they are the hottest of hot paths (tokenize.py's own docstring: "the hot loop of the
whole pipeline"), and this project treats a filesystem read on that path as a real
cost, not a rounding error (see the precompiled-artifact rationale in
``pravapis.artifact``). So the two modules keep hand-written ``frozenset``/``dict``
literals for zero-I/O startup, and this script is what keeps them from silently
drifting out of sync with the data — the same "generated and separately verified"
shape as ``conformance/cases.jsonl`` or the precompiled artifact, just checking a
literal instead of a committed file.

This also re-verifies that Python's own ``str.upper()`` still agrees with the pinned
table for every letter: if a future CPython Unicode database update ever changed that,
this would catch it, instead of the change silently reaching production the next time
someone regenerates something derived from ``.upper()``.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Final

ROOT: Final[Path] = Path(__file__).resolve().parent.parent
CHARS_DIR: Final[Path] = ROOT / "data" / "chars"

sys.path.insert(0, str(ROOT / "src"))


def _data_lines(path: Path) -> Iterator[tuple[int, str]]:
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if line and not line.startswith("#"):
            yield line_no, line


def _read_pairs(path: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line_no, line in _data_lines(path):
        cells = line.split("\t")
        if len(cells) != 2:
            raise ValueError(
                f"{path}:{line_no}: expected 2 tab-separated columns, got {len(cells)}"
            )
        pairs.append((cells[0], cells[1]))
    return pairs


def check_alphabet() -> list[str]:
    # `import pravapis.tokenize as tokenize` would silently resolve to the *function*
    # pravapis.tokenize.tokenize instead of the module: pravapis/__init__.py does
    # `from pravapis.tokenize import tokenize`, which overwrites the `tokenize`
    # attribute Python's import machinery would otherwise set on the `pravapis`
    # package. importlib.import_module goes through sys.modules instead and is not
    # fooled by that.
    tokenize = importlib.import_module("pravapis.tokenize")

    problems: list[str] = []
    pairs = _read_pairs(CHARS_DIR / "alphabet.tsv")
    table_lower = frozenset(lower for lower, _ in pairs)
    table_upper = {lower: upper for lower, upper in pairs}

    if table_lower != tokenize.BELARUSIAN_LETTERS:
        extra = tokenize.BELARUSIAN_LETTERS - table_lower
        missing = table_lower - tokenize.BELARUSIAN_LETTERS
        problems.append(
            "tokenize.BELARUSIAN_LETTERS does not match data/chars/alphabet.tsv "
            f"(extra in code: {sorted(extra)!r}, missing from code: {sorted(missing)!r})"
        )
    for lower, upper in table_upper.items():
        if lower.upper() != upper:
            problems.append(
                f"data/chars/alphabet.tsv says {lower!r} -> {upper!r}, but "
                f"str.upper() now gives {lower.upper()!r} — Python's Unicode data moved"
            )
    return problems


def check_apostrophes() -> list[str]:
    normalize = importlib.import_module("pravapis.normalize")
    tokenize = importlib.import_module("pravapis.tokenize")  # see check_alphabet()

    problems: list[str] = []
    pairs = _read_pairs(CHARS_DIR / "apostrophes.tsv")
    table_chars = frozenset(char for char, _ in pairs)
    canonicals = {canonical for _, canonical in pairs}

    if len(canonicals) != 1:
        problems.append(
            f"data/chars/apostrophes.tsv has more than one canonical value: {canonicals!r}"
        )
        return problems
    (canonical,) = canonicals

    if table_chars != normalize.APOSTROPHES:
        problems.append("normalize.APOSTROPHES does not match data/chars/apostrophes.tsv")
    if canonical != normalize.CANONICAL_APOSTROPHE:
        problems.append(
            f"normalize.CANONICAL_APOSTROPHE is {normalize.CANONICAL_APOSTROPHE!r}, "
            f"but data/chars/apostrophes.tsv says {canonical!r}"
        )
    if frozenset(tokenize.APOSTROPHE_CLASS) != table_chars:
        problems.append("tokenize.APOSTROPHE_CLASS does not match data/chars/apostrophes.tsv")
    return problems


def check_homoglyphs() -> list[str]:
    normalize = importlib.import_module("pravapis.normalize")  # see check_alphabet()

    problems: list[str] = []
    pairs = _read_pairs(CHARS_DIR / "homoglyphs.tsv")
    forward = {latin: cyrillic for latin, cyrillic in pairs}
    reverse = {cyrillic: latin for latin, cyrillic in pairs}

    if forward != normalize.HOMOGLYPH_MAP:
        problems.append("normalize.HOMOGLYPH_MAP does not match data/chars/homoglyphs.tsv")
    if reverse != normalize.REVERSE_HOMOGLYPH_MAP:
        problems.append(
            "normalize.REVERSE_HOMOGLYPH_MAP does not match data/chars/homoglyphs.tsv reversed"
        )
    return problems


def main() -> int:
    if not CHARS_DIR.is_dir():
        print(f"{CHARS_DIR} does not exist; nothing to check")
        return 0

    problems = check_alphabet() + check_apostrophes() + check_homoglyphs()

    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print(f"  {p}")
        print(
            "\ntokenize.py/normalize.py's character-class literals have drifted from "
            "data/chars/*.tsv, which is the normative source. Update the literal to "
            "match the table (or the table, if the table is what's wrong) — never let "
            "them disagree, since every other implementation reads the table."
        )
        return 1
    print("ok — tokenize.py/normalize.py literals match data/chars/*.tsv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
