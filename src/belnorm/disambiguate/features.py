"""Feature extraction for the disambiguation classifier.

Character n-grams of the word itself carry most of the signal (Greco-Latin
stems look nothing like Slavic ones), with a little context — the next
word's length and stress heuristic — for the clitic cases.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from belnorm.rules.morphology import is_first_syllable_stressed, syllable_count
from belnorm.types import Token, TokenKind


def char_ngrams(word: str, n: int = 3) -> list[str]:
    padded = f"^{word}$"
    if len(padded) < n:
        return [padded]
    return [padded[i : i + n] for i in range(len(padded) - n + 1)]


def suffix_features(word: str, k: int = 4) -> dict[str, bool]:
    return {f"suf{i}={word[-i:]}": True for i in range(1, min(k, len(word)) + 1)}


def prefix_features(word: str, k: int = 3) -> dict[str, bool]:
    return {f"pre{i}={word[:i]}": True for i in range(1, min(k, len(word)) + 1)}


def _split_context(token: Token, context: Sequence[Token]) -> tuple[list[Token], list[Token]]:
    left = [t for t in context if t.end <= token.start and t.kind is TokenKind.WORD]
    right = [t for t in context if t.start >= token.end and t.kind is TokenKind.WORD]
    return left, right


def extract_features(token: Token, context: Sequence[Token]) -> dict[str, Any]:
    word = token.text.lower()
    feats: dict[str, Any] = {}
    for n in (2, 3, 4):
        for gram in char_ngrams(word, n):
            key = f"ng{n}={gram}"
            feats[key] = feats.get(key, 0) + 1
    feats.update(suffix_features(word))
    feats.update(prefix_features(word))
    feats["len"] = len(word)
    feats["syll"] = syllable_count(word)
    feats["has_apos"] = "’" in word
    feats["has_hyphen"] = "-" in word
    feats["has_e"] = "э" in word
    feats["has_yo"] = "ё" in word

    left, right = _split_context(token, context)
    if left:
        prev = left[-1].text.lower()
        feats[f"prev={prev}"] = True
    if right:
        nxt = right[0].text.lower()
        feats[f"next={nxt}"] = True
        feats["next_syll"] = syllable_count(nxt)
        feats["next_stress_first"] = is_first_syllable_stressed(nxt)
        feats[f"next_pre2={nxt[:2]}"] = True
    else:
        feats["no_next"] = True
    return feats


def featurize_batch(items: Sequence[tuple[Token, list[Token]]]) -> list[dict[str, Any]]:
    return [extract_features(tok, ctx) for tok, ctx in items]
