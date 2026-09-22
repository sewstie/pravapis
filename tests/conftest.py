from __future__ import annotations

from pathlib import Path

import pytest

from pravapis.config import Config
from pravapis.lexicon.stems import StemIndex
from pravapis.lexicon.store import Lexicon
from pravapis.pipeline import Converter
from pravapis.rules.engine import RuleEngine
from pravapis.rules.loanwords import build_stem_indexes
from pravapis.stress import StressTable
from pravapis.types import Orthography

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def config() -> Config:
    # Always build from TSV so tests never depend on a compiled lexicon or a model.
    return Config(
        lexicon=DATA_DIR / "lexicon",
        rules=tuple(
            DATA_DIR / "rules" / n
            for n in ("palatalization.yaml", "loanwords.yaml", "morphology.yaml")
        ),
        stress=DATA_DIR / "stress",
        morphology=DATA_DIR / "morphology",
        case_forms=DATA_DIR / "lexicon" / "case",
        stems=DATA_DIR / "lexicon" / "stems",
        model=None,
    )


@pytest.fixture(scope="session")
def stress(config: Config) -> StressTable:
    assert config.stress is not None
    return StressTable.load(config.stress)


@pytest.fixture(scope="session")
def stem_indexes(config: Config) -> dict[Orthography, StemIndex]:
    return build_stem_indexes(config.stems)


@pytest.fixture(scope="session")
def engine(config: Config, stem_indexes: dict[Orthography, StemIndex]) -> RuleEngine:
    return RuleEngine.from_yaml(*config.rules, stems=stem_indexes)


@pytest.fixture(scope="session")
def lexicon(config: Config) -> Lexicon:
    return Lexicon.load(config.lexicon)


@pytest.fixture(scope="session")
def converter(
    lexicon: Lexicon, engine: RuleEngine, config: Config, stress: StressTable
) -> Converter:
    from pravapis.lexicon.case_forms import CaseForms
    from pravapis.morphology import MentSuffix
    from pravapis.rules.function_words import FunctionWords

    function_words = FunctionWords.load(DATA_DIR)

    assert config.case_forms is not None
    assert config.morphology is not None
    return Converter(
        lexicon,
        engine,
        None,
        config,
        stress,
        case_forms=CaseForms.load(config.case_forms, function_words.dative_locative_prepositions),
        function_words=function_words,
        ment_suffix=MentSuffix.load(config.morphology),
    )
