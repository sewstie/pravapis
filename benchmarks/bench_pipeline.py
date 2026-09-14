"""pytest-benchmark suite: ``uv run pytest benchmarks/ --benchmark-enable``.

Measures the three hot paths in isolation (tokenize, rule engine, lexicon
lookup) plus the full cascade, so a regression can be pinned to a stage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from belnorm.config import Config
from belnorm.metrics import read_gold
from belnorm.pipeline import Converter
from belnorm.tokenize import tokenize
from belnorm.types import Orthography

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def converter() -> Converter:
    return Converter.from_config(Config.default(DATA))


@pytest.fixture(scope="module")
def corpus() -> str:
    sentences = [n for n, _ in read_gold(DATA / "eval" / "gold.tsv")]
    text = "\n".join(sentences) + "\n"
    reps = 1_000_000 // len(text.encode("utf-8")) + 1
    return text * reps  # ~1 MB


def test_bench_tokenize(benchmark: Any, corpus: str) -> None:
    benchmark(tokenize, corpus)


def test_bench_rule_engine(benchmark: Any, converter: Converter) -> None:
    words = ["снег", "свіння", "здзейсніць", "рассцілаць", "дом", "тэатр", "еўропа"]

    def run() -> None:
        for w in words:
            converter.engine.apply(w, Orthography.TARASKIEVICA)

    benchmark(run)


def test_bench_lexicon_lookup(benchmark: Any, converter: Converter) -> None:
    words = ["мінск", "сістэма", "клас", "дом", "снег", "тэатр"]

    def run() -> None:
        for w in words:
            converter.lexicon.lookup_ci(w, Orthography.TARASKIEVICA)

    benchmark(run)


def test_bench_convert_1mb(benchmark: Any, converter: Converter, corpus: str) -> None:
    result = benchmark(converter.convert, corpus, Orthography.TARASKIEVICA)
    nbytes = len(corpus.encode("utf-8"))
    benchmark.extra_info["mb"] = nbytes / 1e6
    benchmark.extra_info["words"] = sum(result.stats.values())
