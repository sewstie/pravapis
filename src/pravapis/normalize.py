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

from pravapis.types import Script

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

#: The same folding for Latin-script input. A Łacinka text typed on a Belarusian
#: layout picks up Cyrillic look-alikes exactly as Cyrillic text picks up Latin ones.
#: Only the unambiguous pairs are listed: Cyrillic с → Latin c, never Latin s.
REVERSE_HOMOGLYPH_MAP: Final[dict[str, str]] = {
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "у": "y",
    "х": "x",
    "і": "i",
    "А": "A",
    "Е": "E",
    "О": "O",
    "Р": "P",
    "С": "C",
    "У": "Y",
    "Х": "X",
    "І": "I",
    "Т": "T",
    "Н": "H",
    "К": "K",
    "М": "M",
    "В": "B",
}

_LETTER_RUN: Final[regex.Pattern[str]] = regex.compile(r"\p{L}+")
_HAS_CYRILLIC: Final[regex.Pattern[str]] = regex.compile(r"\p{Cyrillic}")
_HAS_LATIN: Final[regex.Pattern[str]] = regex.compile(r"\p{Latin}")
#: Cheap pre-checks: ordinary Belarusian text contains none of these, so the common case
#: returns the run untouched instead of rebuilding it character by character.
_ANY_HOMOGLYPH: Final[regex.Pattern[str]] = regex.compile(
    "[" + regex.escape("".join(HOMOGLYPH_MAP)) + "]"
)
_ANY_REVERSE_HOMOGLYPH: Final[regex.Pattern[str]] = regex.compile(
    "[" + regex.escape("".join(REVERSE_HOMOGLYPH_MAP)) + "]"
)
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
    if not _ANY_HOMOGLYPH.search(run) or not _HAS_CYRILLIC.search(run):
        return run
    return "".join(HOMOGLYPH_MAP.get(ch, ch) for ch in run)


def _fold_run_latin(match: regex.Match[str]) -> str:
    run = match.group(0)
    if not _ANY_REVERSE_HOMOGLYPH.search(run) or not _HAS_LATIN.search(run):
        return run
    return "".join(REVERSE_HOMOGLYPH_MAP.get(ch, ch) for ch in run)


def fold_homoglyphs(text: str, script: Script = Script.CYRILLIC) -> str:
    """Fold look-alike letters towards ``script`` inside mixed-script letter runs.

    A run with no letter of the target script is left alone, so a genuine Latin word
    inside Cyrillic text (and vice versa) survives untouched.
    """
    if script.is_latin:
        return _LETTER_RUN.sub(_fold_run_latin, text)
    return _LETTER_RUN.sub(_fold_run, text)


def normalize_apostrophes(text: str, target: str = CANONICAL_APOSTROPHE) -> str:
    return _APOSTROPHE_RE.sub(target, text)


def strip_zero_width(text: str) -> str:
    return _ZERO_WIDTH_RE.sub("", text)


def sanitize(text: str, script: Script = Script.CYRILLIC) -> str:
    """Compose all four normalisations.

    Order matters: zero-width characters are stripped *before* homoglyph folding so an
    invisible joiner cannot split a letter run in two.

    ``script`` decides which way homoglyphs fold. The default is bit-for-bit what
    pravapis has always done; a Latin script folds the other way, for text arriving in
    Łacinka on the reverse path. Everything else is script-independent: NFC, apostrophes
    and zero-width characters behave the same either way, so ``sanitize`` stays
    idempotent per script.
    """
    return normalize_apostrophes(fold_homoglyphs(strip_zero_width(to_nfc(text)), script))
