"""The classifier is opt-in: the default path never reaches Method.MODEL."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pravapis.config import Config
from pravapis.metrics import read_gold
from pravapis.pipeline import Converter
from pravapis.types import Method, Orthography


def test_default_config_has_no_model(data_dir: Path) -> None:
    assert Config.default().model is None
    assert Config.default(data_dir).model is None


def test_default_converter_never_uses_model(data_dir: Path) -> None:
    converter = Converter.from_config()
    assert converter.disambiguator is None
    assert converter.model_version is None
    for n, t in read_gold(data_dir / "eval" / "gold.tsv"):
        for d, text in ((Orthography.TARASKIEVICA, n), (Orthography.NARKAMAUKA, t)):
            assert converter.convert(text, d).stats[Method.MODEL] == 0


def test_core_import_does_not_load_disambiguate() -> None:
    code = (
        "import sys, pravapis, pravapis.pipeline, pravapis.api.main; "
        "pravapis.convert('план', pravapis.Orthography.TARASKIEVICA); "
        "print(any(m.startswith('pravapis.disambiguate') for m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
