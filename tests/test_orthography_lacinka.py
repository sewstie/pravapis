"""Shared Python/JavaScript examples across both conversion layers."""

import json
from pathlib import Path

import pytest

from pravapis.pipeline import Converter
from pravapis.translit import Transliterator
from pravapis.types import Orthography, Script

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "orthography_lacinka.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize(("nark", "tarask", "latin"), CASES)
def test_conversion_and_lacinka_roundtrip(
    converter: Converter, data_dir: Path, nark: str, tarask: str, latin: str
) -> None:
    forward = Transliterator.load(Script.LACINKA, data_dir=data_dir)
    reverse = Transliterator.load(Script.LACINKA, reverse=True, data_dir=data_dir)
    for case in (str.lower, str.title, str.upper):
        classical = converter.convert(case(nark), Orthography.TARASKIEVICA).text
        assert classical == case(tarask)
        encoded = forward.transliterate(classical).text
        assert encoded == case(latin)
        decoded = reverse.transliterate(encoded).text
        assert decoded == classical
        assert converter.convert(decoded, Orthography.NARKAMAUKA).text == case(nark)
