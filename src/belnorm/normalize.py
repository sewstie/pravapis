"""Unicode hygiene applied exactly once at every input boundary.

Real-world Belarusian text arrives with Latin homoglyphs typed on the wrong
keyboard layout, half a dozen different apostrophes, zero-width joiners from
copy-paste, and mixed NFC/NFD composition. ``sanitize`` folds all of that into
one canonical form so every later stage can match on exact code points.
"""

from __future__ import annotations

import unicodedata
from typing import Final

import regex

# Latin letters that are visually identical to Cyrillic ones and routinely get
# typed inside Cyrillic words. Only folded inside runs that already contain
# Cyrillic, so genuine Latin words are untouched.
HOMOGLYPH_MAP: Final[dict[str, str]] = {
    "a": "а",
    "e": "е",
    "o": "о",
    "p": "р",
    "c": "с",
    "y": "у",
    "x": "х",
    "i": "і",
    "A": "А",
    "E": "Е",
    "O": "О",
    "P": "Р",
    "C": "С",
    "Y": "У",
    "X": "Х",
    "I": "І",
    "T": "Т",
    "H": "Н",
    "K": "К",
    "M": "М",
    "B": "В",
}

CANONICAL_APOSTROPHE: Final[str] = "’"

APOSTROPHES: Final[frozenset[str]] = frozenset(
    {
        "’",  # RIGHT SINGLE QUOTATION MARK (canonical)
        "'",  # APOSTROPHE
        "ʼ",  # MODIFIER LETTER APOSTROPHE
        "`",  # GRAVE ACCENT
        "‘",  # LEFT SINGLE QUOTATION MARK (common typo)
    }
)

ZERO_WIDTH: Final[frozenset[str]] = frozenset(
    {
        "​",  # ZERO WIDTH SPACE
        "‌",  # ZERO WIDTH NON-JOINER
        "‍",  # ZERO WIDTH JOINER
        "⁠",  # WORD JOINER
        "﻿",  # BYTE ORDER MARK
        "­",  # SOFT HYPHEN
    }
)

_LETTER_RUN: Final[regex.Pattern[str]] = regex.compile(r"\p{L}+")
_HAS_CYRILLIC: Final[regex.Pattern[str]] = regex.compile(r"\p{Cyrillic}")
_APOSTROPHE_RE: Final[regex.Pattern[str]] = regex.compile(
    "[" + "".join(regex.escape(a) for a in sorted(APOSTROPHES)) + "]"
)
_ZERO_WIDTH_RE: Final[regex.Pattern[str]] = regex.compile(
    "[" + "".join(regex.escape(z) for z in sorted(ZERO_WIDTH)) + "]"
)


def to_nfc(text: str) -> str:
    """Canonical composition: й as one code point, not и + combining breve."""
    return unicodedata.normalize("NFC", text)


def _fold_run(match: regex.Match[str]) -> str:
    run = match.group(0)
    if not _HAS_CYRILLIC.search(run):
        return run
    return "".join(HOMOGLYPH_MAP.get(ch, ch) for ch in run)


def fold_homoglyphs(text: str) -> str:
    """Replace Latin look-alikes with Cyrillic inside mixed-script letter runs."""
    return _LETTER_RUN.sub(_fold_run, text)


def normalize_apostrophes(text: str, target: str = CANONICAL_APOSTROPHE) -> str:
    return _APOSTROPHE_RE.sub(target, text)


def strip_zero_width(text: str) -> str:
    return _ZERO_WIDTH_RE.sub("", text)


def sanitize(text: str) -> str:
    """Compose all four normalisations.

    Order matters: zero-width characters are stripped *before* homoglyph
    folding so an invisible joiner cannot split a letter run in two.
    """
    return normalize_apostrophes(fold_homoglyphs(strip_zero_width(to_nfc(text))))
