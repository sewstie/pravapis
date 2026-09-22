from __future__ import annotations

from itertools import pairwise

import pytest

from pravapis.tokenize import context_of, detokenize, is_belarusian_word, next_word, tokenize
from pravapis.types import Token, TokenKind


def kinds(text: str) -> list[tuple[str, TokenKind]]:
    return [(t.text, t.kind) for t in tokenize(text)]


def test_basic_sentence() -> None:
    assert kinds("Ішоў снег.") == [
        ("Ішоў", TokenKind.WORD),
        (" ", TokenKind.SPACE),
        ("снег", TokenKind.WORD),
        (".", TokenKind.PUNCT),
    ]


def test_apostrophe_and_hyphen_stay_inside_words() -> None:
    assert kinds("з’ява па-беларуску") == [
        ("з’ява", TokenKind.WORD),
        (" ", TokenKind.SPACE),
        ("па-беларуску", TokenKind.WORD),
    ]


def test_trailing_hyphen_is_punctuation() -> None:
    assert kinds("снег-") == [("снег", TokenKind.WORD), ("-", TokenKind.PUNCT)]


def test_numbers_latin_and_punct_runs() -> None:
    assert kinds("У 2024 г. — Wi-Fi!?") == [
        ("У", TokenKind.WORD),
        (" ", TokenKind.SPACE),
        ("2024", TokenKind.NUMBER),
        (" ", TokenKind.SPACE),
        ("г", TokenKind.WORD),
        (".", TokenKind.PUNCT),
        (" ", TokenKind.SPACE),
        ("—", TokenKind.PUNCT),
        (" ", TokenKind.SPACE),
        ("Wi-Fi", TokenKind.LATIN),
        ("!?", TokenKind.PUNCT),
    ]


def test_offsets_are_contiguous() -> None:
    text = "Снег, снег\nі лёд."
    tokens = tokenize(text)
    assert tokens[0].start == 0
    for prev, cur in pairwise(tokens):
        assert prev.end == cur.start
    assert tokens[-1].end == len(text)


@pytest.mark.parametrize("text", ["", "снег", "  \n\t", "🙂 снег 🙂", "áбв", "з'ява—так"])
def test_detokenize_roundtrip(text: str) -> None:
    assert detokenize(tokenize(text)) == text


def test_is_belarusian_word_rejects_russian_letters() -> None:
    assert is_belarusian_word(Token("снег", 0, 4, TokenKind.WORD))
    assert is_belarusian_word(Token("з’ява", 0, 5, TokenKind.WORD))
    assert not is_belarusian_word(Token("привет", 0, 6, TokenKind.WORD))  # и
    assert not is_belarusian_word(Token("щука", 0, 4, TokenKind.WORD))  # щ
    assert not is_belarusian_word(Token("снег", 0, 4, TokenKind.LATIN))


def test_context_of_skips_non_words() -> None:
    tokens = tokenize("адзін, два тры чатыры пяць")
    i = next(k for k, t in enumerate(tokens) if t.text == "тры")
    assert [t.text for t in context_of(tokens, i, window=2)] == ["адзін", "два", "чатыры", "пяць"]
    assert [t.text for t in context_of(tokens, i, window=1)] == ["два", "чатыры"]


def test_next_word_breaks_on_punctuation() -> None:
    tokens = tokenize("не быў")
    assert next_word(tokens, 0) is not None
    assert next_word(tokens, 0).text == "быў"  # type: ignore[union-attr]
    tokens = tokenize("не, быў")
    assert next_word(tokens, 0) is None
    assert next_word(tokens, len(tokens) - 1) is None


def test_next_word_crosses_a_quotation_mark() -> None:
    """§13 Заўвага: двукосье is not a punctuation mark, so it is not a break.

    An opening quote is silent, and a clitic agrees with what is spoken. Found in the
    parallel corpus as з «Віцебскам», which be-tarask writes зь.
    """
    tokens = tokenize("з «Віцебскам»")
    assert next_word(tokens, 0) is not None
    assert next_word(tokens, 0).text == "Віцебскам"  # type: ignore[union-attr]


def test_next_word_still_breaks_on_a_dash() -> None:
    """A працяжнік *is* a punctuation mark. §13 names злучок and двукосье, not this."""
    assert next_word(tokenize("з — снегам"), 0) is None
