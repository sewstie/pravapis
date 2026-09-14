"""Capitalisation patterns: detect one on the input word, re-apply it to the output.

Conversion always works on lowercase forms (the lexicon is stored lowercase
and rules are written lowercase), so the original case has to survive
round-tripping through the cascade.
"""

from __future__ import annotations

from typing import Literal

CaseForm = Literal["lower", "upper", "title", "mixed"]


def detect_case(word: str) -> CaseForm:
    letters = [c for c in word if c.isalpha()]
    if not letters:
        return "lower"
    if all(c.islower() for c in letters):
        return "lower"
    if letters[0].isupper() and all(c.islower() for c in letters[1:]):
        return "title"
    if all(c.isupper() for c in letters):
        # A single capital letter ("Я", "У") is ambiguous; treat it as title
        # so "У Менску" does not come back as "У МЕНСКУ".
        return "title" if len(letters) == 1 else "upper"
    return "mixed"


def apply_case(word: str, form: CaseForm) -> str:
    match form:
        case "lower":
            return word
        case "upper":
            return word.upper()
        case "title":
            for i, c in enumerate(word):
                if c.isalpha():
                    return word[:i] + c.upper() + word[i + 1 :]
            return word
        case "mixed":
            return word


def recase(source: str, target: str) -> str:
    """Give ``target`` (lowercase) the capitalisation pattern of ``source``."""
    return apply_case(target, detect_case(source))
