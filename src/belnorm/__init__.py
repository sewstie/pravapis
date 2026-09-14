"""belnorm — bidirectional Belarusian orthography converter (Narkamaŭka ↔ Taraškievica).

>>> from belnorm import convert, Orthography
>>> convert("снег", Orthography.TARASKIEVICA)
'сьнег'
"""

from __future__ import annotations

__version__ = "0.1.0"

from belnorm.normalize import sanitize
from belnorm.pipeline import Converter, convert, default_converter
from belnorm.tokenize import detokenize, tokenize
from belnorm.types import Conversion, ConversionResult, Method, Orthography, Token, TokenKind

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
