from __future__ import annotations

from pathlib import Path

import pytest

from belnorm.config import Config
from belnorm.disambiguate.features import (
    char_ngrams,
    extract_features,
    prefix_features,
    suffix_features,
)
from belnorm.disambiguate.labels import KEEP, LABELS, apply_label, derive_label
from belnorm.disambiguate.train import derive_label_with_rules, load_training_pairs, locate
from belnorm.lexicon.store import Lexicon
from belnorm.pipeline import Converter
from belnorm.rules.engine import RuleEngine
from belnorm.tokenize import tokenize
from belnorm.types import Method, Orthography, Token, TokenKind

sklearn = pytest.importorskip("sklearn")
N2T = Orthography.TARASKIEVICA


@pytest.mark.parametrize(
    ("word", "label", "expected"),
    [
        ("план", "soft_l", "плян"),
        ("логіка", "soft_l", "лёгіка"),
        ("клуб", "soft_l", "клюб"),
        ("балкон", "soft_l", "балькон"),
        ("сістэма", "i_to_y", "сыстэма"),
        ("метр", "e_to_e", "мэтр"),
        ("не", "particle", "ня"),
        ("без", "particle", "бяз"),
        ("дом", "keep", "дом"),
        ("дом", "soft_l", "дом"),
    ],
)
def test_apply_label(word: str, label: str, expected: str) -> None:
    assert apply_label(word, label) == expected


def test_apply_label_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        apply_label("дом", "nope")


def test_derive_label() -> None:
    assert derive_label("план", "плян") == "soft_l"
    assert derive_label("сістэма", "сыстэма") == "i_to_y"
    assert derive_label("не", "ня") == "particle"
    assert derive_label("лапа", "лапа") == KEEP
    assert derive_label("снег", "сьнег") is None  # that's a rule, not an operation


def test_derive_label_with_rules(engine: RuleEngine) -> None:
    assert derive_label_with_rules("снег", "сьнег", engine) == KEEP
    assert derive_label_with_rules("метр", "мэтар", engine) == "e_to_e"  # e_to_e + тр→тар
    assert derive_label_with_rules("план", "плян", engine) == "soft_l"  # not keep, despite the rule
    assert derive_label_with_rules("без", "бязь", engine) == "particle"
    assert derive_label_with_rules("феномен", "фэномэн", engine) is None


def test_feature_helpers() -> None:
    assert char_ngrams("аб", 3) == ["^аб", "аб$"]
    assert char_ngrams("а", 4) == ["^а$"]
    assert suffix_features("план", 2) == {"suf1=н": True, "suf2=ан": True}
    assert prefix_features("план", 2) == {"pre1=п": True, "pre2=пл": True}


def test_extract_features_uses_context_sides() -> None:
    tokens = tokenize("я не быў")
    ne = tokens[2]
    feats = extract_features(ne, [tokens[0], tokens[4]])
    assert feats["prev=я"] is True
    assert feats["next=быў"] is True
    assert feats["next_stress_first"] is True
    assert feats["next_syll"] == 1
    lonely = extract_features(Token("не", 0, 2, TokenKind.WORD), [])
    assert lonely["no_next"] is True


def test_locate_falls_back_to_bare_token() -> None:
    tok, ctx = locate("план", "У нас ёсць план на заўтра")
    assert tok.text == "план"
    assert [t.text for t in ctx] == ["нас", "ёсць", "на", "заўтра"]
    tok, ctx = locate("план", "")
    assert tok.text == "план" and ctx == []


def test_load_training_pairs(engine: RuleEngine, data_dir: Path) -> None:
    X, y = load_training_pairs(data_dir / "eval" / "ambiguous.tsv", engine)
    assert len(X) == len(y) > 100
    assert set(y) == set(LABELS)


@pytest.fixture(scope="module")
def trained(engine: RuleEngine, data_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    from belnorm.disambiguate import train as tr

    X, y = load_training_pairs(data_dir / "eval" / "ambiguous.tsv", engine)
    model = tr.train(X, y)
    out = tmp_path_factory.mktemp("model") / "disambig.joblib"
    tr.save_model(model, out)
    report = tr.cross_validate(X, y, folds=3)
    assert report.folds == 3 and 0.0 < report.mean <= 1.0
    return out


def test_model_in_cascade(
    trained: Path, lexicon: Lexicon, engine: RuleEngine, config: Config
) -> None:
    from belnorm.disambiguate.predict import Disambiguator

    cfg = config.model_copy(update={"model": trained})
    converter = Converter(lexicon, engine, Disambiguator.load(trained), cfg)
    assert converter.model_version
    result = converter.convert("Лабірынт быў складаны. Лапа ката.", N2T)
    by_source = {c.source: c for c in result.conversions}
    assert by_source["Лабірынт"].target == "Лябірынт"
    assert by_source["Лабірынт"].method is Method.MODEL
    assert 0.75 <= by_source["Лабірынт"].confidence <= 1.0
    assert by_source["Лапа"].method is Method.IDENTITY  # identity set short-circuits the model
    # Batched (text-level) and single-word paths agree.
    assert converter.convert_word("Лабірынт", N2T).target == "Лябірынт"
    (e,) = converter.explain("лабірынт", N2T)
    assert e.method is Method.MODEL and e.traces[0].rule_id.startswith("model:soft_l")


def test_unconfident_prediction_is_silence(trained: Path) -> None:
    from belnorm.disambiguate.predict import Disambiguator

    d = Disambiguator.load(trained, threshold=1.01)  # nothing can pass
    word, score = d.predict(Token("лабірынт", 0, 8, TokenKind.WORD), [])
    assert word == "лабірынт"
    assert not d.is_confident(score)


def test_from_config_survives_missing_model(config: Config, tmp_path: Path) -> None:
    cfg = config.model_copy(update={"model": tmp_path / "nope.joblib"})
    converter = Converter.from_config(cfg)
    assert converter.disambiguator is None
    assert converter.convert("снег", N2T).text == "сьнег"
