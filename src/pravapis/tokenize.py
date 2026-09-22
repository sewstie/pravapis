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

from pravapis.types import Token, TokenKind

#: Kept in sync with data/chars/apostrophes.tsv (the `char` column) by
#: scripts/check_charclass_sync.py — see that file for why this is a literal here
#: rather than something read off disk.
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

#: Keyed by ``Match.lastgroup``, which is typed ``str | None``. Every branch of
#: _TOKEN_RE is a named group, so None cannot occur; a KeyError would be loud if it did.
_KIND_BY_GROUP: Final[dict[str | None, TokenKind]] = {
    "word": TokenKind.WORD,
    "latin": TokenKind.LATIN,
    "number": TokenKind.NUMBER,
    "space": TokenKind.SPACE,
    "punct": TokenKind.PUNCT,
    "other": TokenKind.PUNCT,
}

# Letters of the Belarusian alphabet, both orthographies (ґ is Taraškievica-only).
# Kept in sync with data/chars/alphabet.tsv (the `lower` column) by
# scripts/check_charclass_sync.py — that file is NORMATIVE; this is a hand-written
# copy for zero-I/O startup on the hottest path in the pipeline.
BELARUSIAN_LETTERS: Final[frozenset[str]] = frozenset("абвгґдеёжзійклмнопрстуўфхцчшыьэюя")
_WORD_CHARS: Final[frozenset[str]] = BELARUSIAN_LETTERS | frozenset(APOSTROPHE_CLASS + "-")
#: The same set as a negated character class, both cases, so membership is one regex
#: search over the token rather than a genexpr allocating per character.
_NOT_BELARUSIAN: Final[regex.Pattern[str]] = regex.compile(
    "[^" + regex.escape("".join(sorted(_WORD_CHARS | {c.upper() for c in _WORD_CHARS}))) + "]"
)


def tokenize(text: str) -> list[Token]:
    # The hot loop of the whole pipeline: one Token per match over the entire input.
    # Locals for the attribute lookups, span() for one call instead of start()+end(),
    # and no str() around lastgroup, which is already a string.
    tokens: list[Token] = []
    append = tokens.append
    kinds = _KIND_BY_GROUP
    for m in _TOKEN_RE.finditer(text):
        start, end = m.span()
        append(Token(text[start:end], start, end, kinds[m.lastgroup]))
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
    return not _NOT_BELARUSIAN.search(token.text)


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


def previous_word(tokens: Sequence[Token], i: int) -> Token | None:
    """The last word token before index ``i`` with only whitespace in between."""
    for j in range(i - 1, -1, -1):
        if tokens[j].kind is TokenKind.WORD:
            return tokens[j]
        if tokens[j].kind is not TokenKind.SPACE:
            return None
    return None


def next_word(tokens: Sequence[Token], i: int) -> Token | None:
    """The first word token after index ``i``, across whitespace and §13 bridges.

    Punctuation breaks the clitic relationship: "не, быў" is not "ня быў". A quotation
    mark is not punctuation for this purpose — §13 Заўвага says so in as many words, and
    the clitic hears what is spoken, where an opening quote is silent. So
    ``з «Віцебскам»`` softens exactly as ``з Віцебскам`` does; be-tarask writes
    зь in both. See :func:`bridges_words` for which marks are transparent.
    """
    for j in range(i + 1, len(tokens)):
        if tokens[j].kind is TokenKind.WORD:
            return tokens[j]
        if not bridges_words(tokens, j):
            return None
    return None


#: Збор 2005 §13 Заўвага: "Злучок і двукоссе не з'яўляюцца знакамі прыпынку і на
#: правапіс й не ўплываюць" — a hyphen (злучок) or a quotation mark (двукоссе) between
#: two words is an invisible bridge, so the conjunction still sees the vowel before it.
#: A dash (працяжнік) is a real punctuation mark and blocks the rule, which is why the
#: en and em dashes are absent here even though they look like long hyphens.
HYPHENS: Final[frozenset[str]] = frozenset("-‐‑­")
QUOTES: Final[frozenset[str]] = frozenset('«»“”„‟‹›"')


def bridges_words(tokens: Sequence[Token], i: int) -> bool:
    """Is ``tokens[i]`` transparent to the §13 conjunction rule?

    True for whitespace and for quotation marks; true for a hyphen only when it is
    written against a word, as in "адна- і шматмоўныя". A hyphen with space on both
    sides is a dash that someone typed on an ASCII keyboard, and a dash blocks the rule.
    """
    token = tokens[i]
    if token.kind is TokenKind.SPACE:
        return True
    if token.kind is not TokenKind.PUNCT:
        return False
    text = token.text
    if all(c in QUOTES for c in text):
        return True
    if not all(c in HYPHENS or c in QUOTES for c in text):
        return False
    touches = (i > 0 and tokens[i - 1].kind is not TokenKind.SPACE) or (
        i + 1 < len(tokens) and tokens[i + 1].kind is not TokenKind.SPACE
    )
    return touches
