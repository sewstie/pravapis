from __future__ import annotations

from pathlib import Path

import pytest

from pravapis.config import Config
from pravapis.lexicon.store import Lexicon
from pravapis.pipeline import Converter
from pravapis.rules.engine import RuleEngine
from pravapis.stress import StressTable

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
        case_forms=DATA_DIR / "lexicon" / "case",
        model=None,
    )


@pytest.fixture(scope="session")
def stress(config: Config) -> StressTable:
    assert config.stress is not None
    return StressTable.load(config.stress)


@pytest.fixture(scope="session")
def engine(config: Config) -> RuleEngine:
    return RuleEngine.from_yaml(*config.rules)


@pytest.fixture(scope="session")
def lexicon(config: Config) -> Lexicon:
    return Lexicon.load(config.lexicon)


@pytest.fixture(scope="session")
def converter(
    lexicon: Lexicon, engine: RuleEngine, config: Config, stress: StressTable
) -> Converter:
    from pravapis.lexicon.case_forms import CaseForms

    assert config.case_forms is not None
    return Converter(
        lexicon, engine, None, config, stress, case_forms=CaseForms.load(config.case_forms)
    )
