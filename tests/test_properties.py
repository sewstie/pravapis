"""Property-based tests (hypothesis).

* tokenizing is lossless for arbitrary Unicode text
* sanitize is idempotent
* the assimilative-softness layer is a bijection: N→T→N is the identity for
  any apostrophe/soft-sign-free word that only palatalization rules touch
* converting never changes the number of tokens, nor any non-word token
"""

from __future__ import annotations

from hypothesis import assume, example, given, settings
from hypothesis import strategies as st

from belnorm.normalize import sanitize
from belnorm.pipeline import Converter
from belnorm.rules.engine import RuleEngine
from belnorm.rules.palatalization import mark_assimilative_softness, unmark_assimilative_softness
from belnorm.tokenize import detokenize, tokenize
from belnorm.types import Orthography, TokenKind

N2T = Orthography.TARASKIEVICA
T2N = Orthography.NARKAMAUKA

BELARUSIAN_ALPHABET = "абвгдеёжзійклмнопрстуўфхцчшыьэюя’- \n.,!?"
# Letters a Narkamaŭka word can contain before any softness is marked.
NARK_LETTERS = "абвгдежзійклмнопрстуўфхцчшыэюяё’"


def belarusian_text() -> st.SearchStrategy[str]:
    return st.text(alphabet=BELARUSIAN_ALPHABET, min_size=1, max_size=40)


def belarusian_words() -> st.SearchStrategy[str]:
    return st.text(alphabet=NARK_LETTERS, min_size=1, max_size=12)


@given(st.text())
def test_tokenize_is_lossless_for_any_text(s: str) -> None:
    assert detokenize(tokenize(s)) == s


@given(belarusian_text())
def test_tokenize_is_lossless_for_belarusian(s: str) -> None:
    assert detokenize(tokenize(s)) == s


@given(st.text())
def test_sanitize_is_idempotent(s: str) -> None:
    once = sanitize(s)
    assert sanitize(once) == once


@given(belarusian_words())
@example("зллю")
def test_softness_functions_round_trip(w: str) -> None:
    # дздз is ambiguous with ддз on the way back; Narkamaŭka never writes it.
    assume("дздз" not in w)
    marked = mark_assimilative_softness(w)
    assert unmark_assimilative_softness(marked) == w


@given(belarusian_words())
def test_mark_is_idempotent(w: str) -> None:
    once = mark_assimilative_softness(w)
    assert mark_assimilative_softness(once) == once


@settings(max_examples=300)
@given(belarusian_words())
@example("зллю")  # assimilation across a soft geminate: зьльлю
def test_engine_palatalization_round_trip(engine: RuleEngine, w: str) -> None:
    assume("дздз" not in w)
    there, fired = engine.apply(w, N2T)
    assume(all(r.startswith("palat.") for r in fired))
    back, fired_back = engine.apply(there, T2N)
    assume(all(r.startswith("palat.") for r in fired_back))
    assert back == w


@settings(max_examples=300)
@given(
    st.sampled_from(["з", "праз", "цераз"]),
    st.text(alphabet=NARK_LETTERS[:-1], min_size=1, max_size=10),
)
def test_preposition_softness_follows_converted_next_word(
    converter: Converter, prep: str, w: str
) -> None:
    """з/праз/цераз take ь exactly when the next word, as written in Taraškievica, has a soft onset.

    The palatalization bug class (зллю, без слёз): a condition evaluated on the
    Narkamaŭka form, where assimilative softness is not written.
    """
    from belnorm.rules.morphology import CLITICS, _soft_onset

    assume(w not in CLITICS)
    out = converter.convert(f"{prep} {w}", N2T)
    assume(len(out.conversions) == 2)
    head, nxt = out.conversions
    assert (head.target == prep + "ь") is _soft_onset(nxt.target.lower())


@settings(max_examples=200)
@given(belarusian_text())
def test_conversion_preserves_layout(converter: Converter, s: str) -> None:
    s = sanitize(s)
    before = tokenize(s)
    after = tokenize(converter.convert(s, N2T).text)
    assert len(before) == len(after)
    for a, b in zip(before, after, strict=True):
        assert a.kind == b.kind
        if a.kind is not TokenKind.WORD:
            assert a.text == b.text


@settings(max_examples=200)
@given(belarusian_text())
def test_conversion_is_idempotent_in_target(converter: Converter, s: str) -> None:
    once = converter.convert(sanitize(s), N2T).text
    assert converter.convert(once, N2T).text == once
