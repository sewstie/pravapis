"""pravapis — bidirectional Belarusian orthography converter (Narkamaŭka ↔ Taraškievica).

>>> from pravapis import convert, Orthography
>>> convert("снег", Orthography.TARASKIEVICA)
'сьнег'
"""

from __future__ import annotations

__version__ = "0.1.0"

from pravapis.normalize import sanitize
from pravapis.pipeline import Converter, convert, default_converter
from pravapis.tokenize import detokenize, tokenize
from pravapis.types import Conversion, ConversionResult, Method, Orthography, Token, TokenKind

__all__ = [
    "Conversion",
    "ConversionResult",
    "Converter",
    "Method",
    "Orthography",
    "Token",
    "TokenKind",
    "__version__",
    "convert",
    "default_converter",
    "detokenize",
    "sanitize",
    "tokenize",
]
