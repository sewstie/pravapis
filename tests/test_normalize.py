from __future__ import annotations

import unicodedata

import pytest

from pravapis.normalize import (
    fold_homoglyphs,
    normalize_apostrophes,
    sanitize,
    strip_zero_width,
    to_nfc,
)


def test_to_nfc_composes_breve() -> None:
    decomposed = unicodedata.normalize("NFD", "йо")
    assert decomposed != "йо"
    assert to_nfc(decomposed) == "йо"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("cнег", "снег"),  # Latin c inside a Cyrillic word
        ("Mінск", "Мінск"),  # Latin M
        ("iснуе", "існуе"),  # Latin i for і
        ("hello world", "hello world"),  # pure Latin untouched
        ("снег and cat", "снег and cat"),  # Latin word next to Cyrillic word untouched
    ],
)
def test_fold_homoglyphs(raw: str, expected: str) -> None:
    assert fold_homoglyphs(raw) == expected


@pytest.mark.parametrize("apostrophe", ["'", "ʼ", "`", "‘", "’"])
def test_normalize_apostrophes(apostrophe: str) -> None:
    assert normalize_apostrophes(f"з{apostrophe}ява") == "з’ява"


def test_strip_zero_width() -> None:
    assert strip_zero_width("сн​ег﻿") == "снег"
    assert strip_zero_width("па­дарунак") == "падарунак"


def test_sanitize_composes_everything() -> None:
    raw = unicodedata.normalize("NFD", "з'я​ва cнег")
    assert sanitize(raw) == "з’ява снег"


@pytest.mark.parametrize("text", ["снег", "з'ява", "cнег", "Hello, свет!", "", "   "])
def test_sanitize_is_idempotent(text: str) -> None:
    once = sanitize(text)
    assert sanitize(once) == once
