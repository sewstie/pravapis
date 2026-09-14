"""Lossless tokenizer.

``detokenize(tokenize(s)) == s`` for every string ``s`` — the property test
in ``tests/test_properties.py`` enforces it. Every character of the input is
assigned to exactly one token, including whitespace and punctuation, so the
converter can rewrite word tokens in place and reassemble the original layout.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import regex

from belnorm.types import Token, TokenKind

APOSTROPHE_CLASS: Final[str] = "’'ʼ`‘"

# A Belarusian word: Cyrillic runs joined by apostrophes or hyphens
# (з’ява, па-беларуску, што-небудзь). Trailing/leading hyphens stay punctuation.
WORD_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"\p{{Cyrillic}}+(?:[{APOSTROPHE_CLASS}\-]\p{{Cyrillic}}+)*"
)

_TOKEN_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"(?P<word>\p{{Cyrillic}}+(?:[{APOSTROPHE_CLASS}\-]\p{{Cyrillic}}+)*)"
    rf"|(?P<latin>\p{{L}}+(?:[{APOSTROPHE_CLASS}\-]\p{{L}}+)*)"
    r"|(?P<number>\d+(?:[.,]\d+)*)"
    r"|(?P<space>\s+)"
    r"|(?P<punct>[^\p{L}\d\s]+)"
    r"|(?P<other>.)",
    regex.DOTALL,
)

_KIND_BY_GROUP: Final[dict[str, TokenKind]] = {
    "word": TokenKind.WORD,
    "latin": TokenKind.LATIN,
    "number": TokenKind.NUMBER,
    "space": TokenKind.SPACE,
    "punct": TokenKind.PUNCT,
    "other": TokenKind.PUNCT,
}

# Letters of the Belarusian alphabet, both orthographies (ґ is Taraškievica-only).
BELARUSIAN_LETTERS: Final[frozenset[str]] = frozenset("абвгґдеёжзійклмнопрстуўфхцчшыьэюя")
_WORD_CHARS: Final[frozenset[str]] = BELARUSIAN_LETTERS | frozenset(APOSTROPHE_CLASS + "-")


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    for m in _TOKEN_RE.finditer(text):
        kind = _KIND_BY_GROUP[str(m.lastgroup)]
        tokens.append(Token(m.group(0), m.start(), m.end(), kind))
    return tokens


def detokenize(tokens: Sequence[Token]) -> str:
    return "".join(t.text for t in tokens)


def is_belarusian_word(token: Token) -> bool:
    """True when every letter belongs to the Belarusian alphabet.

    Russian/Ukrainian words (и, щ, ъ, ї …) return False and are passed through
    untouched rather than half-converted.
    """
    if token.kind is not TokenKind.WORD:
        return False
    return all(c.lower() in _WORD_CHARS for c in token.text)


def context_of(tokens: Sequence[Token], i: int, window: int = 2) -> list[Token]:
    """The nearest ``window`` word tokens on each side of ``tokens[i]``.

    Non-word tokens are skipped; the token itself is excluded.
    """
    left: list[Token] = []
    j = i - 1
    while j >= 0 and len(left) < window:
        if tokens[j].kind is TokenKind.WORD:
            left.append(tokens[j])
        j -= 1
    left.reverse()
    right: list[Token] = []
    j = i + 1
    while j < len(tokens) and len(right) < window:
        if tokens[j].kind is TokenKind.WORD:
            right.append(tokens[j])
        j += 1
    return left + right


def next_word(tokens: Sequence[Token], i: int) -> Token | None:
    """The first word token after index ``i`` with only whitespace in between.

    Punctuation breaks the clitic relationship: "не, быў" is not "ня быў".
    """
    for j in range(i + 1, len(tokens)):
        if tokens[j].kind is TokenKind.WORD:
            return tokens[j]
        if tokens[j].kind is not TokenKind.SPACE:
            return None
    return None
