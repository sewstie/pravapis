"""pravapis — bidirectional Belarusian orthography converter (Narkamaŭka ↔ Taraškievica),
with Cyrillic ↔ Latin transliteration.

>>> from pravapis import convert
>>> result = convert("снег", {"from": "narkamauka", "to": "taraskievica"})
>>> result.text
'сьнег'
>>> result.to_dict()["changes"][0]["rule"]
'palat.assim'

``convert(text, {"from": …, "to": …}) → {"text": …, "changes": [...]}`` is the frozen
public contract, identical in every implementation of pravapis. See
:class:`pravapis.types.ConversionResult`.

>>> from pravapis import Script, transliterate
>>> transliterate("сьнег", Script.LACINKA)
'śnieh'
"""

from __future__ import annotations

__version__ = "0.1.0"

from pravapis.dataversion import DATA_VERSION
from pravapis.normalize import sanitize
from pravapis.pipeline import Converter, convert, default_converter
from pravapis.tokenize import detokenize, tokenize
from pravapis.translit import Transliterator, transliterate
from pravapis.types import (
    Conversion,
    ConversionResult,
    ConvertOptions,
    Method,
    Orthography,
    Script,
    Token,
    TokenKind,
)

__all__ = [
    "DATA_VERSION",
    "Conversion",
    "ConversionResult",
    "ConvertOptions",
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
