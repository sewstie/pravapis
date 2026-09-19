"""pravapis — bidirectional Belarusian orthography converter (Narkamaŭka ↔ Taraškievica),
with Cyrillic ↔ Latin transliteration.

>>> from pravapis import convert, Orthography
>>> convert("снег", Orthography.TARASKIEVICA)
'сьнег'

>>> from pravapis import Script, transliterate
>>> transliterate("сьнег", Script.LACINKA)
'śnieh'
"""

from __future__ import annotations

__version__ = "0.1.0"

from pravapis.normalize import sanitize
from pravapis.pipeline import Converter, convert, default_converter
from pravapis.tokenize import detokenize, tokenize
from pravapis.translit import Transliterator, transliterate
from pravapis.types import (
    Conversion,
    ConversionResult,
    Method,
    Orthography,
    Script,
    Token,
    TokenKind,
)

__all__ = [
    "Conversion",
    "ConversionResult",
    "Converter",
    "Method",
    "Orthography",
    "Script",
    "Token",
    "TokenKind",
    "Transliterator",
    "__version__",
    "convert",
    "default_converter",
    "detokenize",
    "sanitize",
    "tokenize",
    "transliterate",
]
