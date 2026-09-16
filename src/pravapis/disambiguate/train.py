"""Train the disambiguation classifier.

A linear model on character n-grams: ``DictVectorizer`` → ``LogisticRegression``.
It is explainable (inspect the coefficients per n-gram), trains in seconds, and
is strong enough for a five-way choice between edit operations.

Training data (``data/eval/ambiguous.tsv``)::

    source<TAB>target<TAB>context sentence containing the source word

The label is derived automatically (``labels.derive_label``): which edit
operation, followed by the deterministic rules, turns ``source`` into
``target``. Rows no operation explains are skipped and reported.

Requires the ``ml`` extra: ``pip install pravapis[ml]``.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pravapis import __version__
from pravapis.disambiguate.features import extract_features
from pravapis.disambiguate.labels import KEEP, LABELS, PARTICLE, apply_label
from pravapis.normalize import sanitize
from pravapis.rules.engine import RuleEngine
from pravapis.tokenize import context_of, tokenize
from pravapis.types import Orthography, Token, TokenKind

log = logging.getLogger(__name__)


class MissingMLDependency(RuntimeError):
    pass


def _require_sklearn() -> Any:
    try:
        import sklearn
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise MissingMLDependency("install pravapis[ml] to train or load the model") from exc
    return sklearn


@dataclass(frozen=True, slots=True)
class CVReport:
    folds: int
    accuracies: tuple[float, ...]
    n_samples: int
    label_counts: dict[str, int]

    @property
    def mean(self) -> float:
        return sum(self.accuracies) / len(self.accuracies) if self.accuracies else 0.0

    @property
    def std(self) -> float:
        if len(self.accuracies) < 2:
            return 0.0
        m = self.mean
        variance = sum((a - m) ** 2 for a in self.accuracies) / (len(self.accuracies) - 1)
        return float(variance**0.5)


def derive_label_with_rules(source: str, target: str, engine: RuleEngine | None) -> str | None:
    """Which operation, followed by the rules, maps ``source`` to ``target``?"""
    source, target = source.lower(), target.lower()

    def finish(word: str) -> str:
        return engine.apply(word, Orthography.TARASKIEVICA)[0] if engine else word

    # Edit operations are tried first so a loan the stem rules already cover
    # (план → плян) still teaches the classifier "soft_l", not "keep".
    for label in LABELS[1:]:
        edited = apply_label(source, label)
        if edited == source:
            continue
        finished = finish(edited)
        # бяз → бязь: the preposition softening is contextual and applied by
        # the pipeline, not the engine, so accept it here too.
        if finished == target or (label == PARTICLE and finished + "ь" == target):
            return label
    if finish(source) == target:
        return KEEP
    return None


def read_training_rows(path: Path) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            line = raw.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                raise ValueError(f"{path}:{line_no}: expected at least two columns")
            source, target = sanitize(parts[0].strip()), sanitize(parts[1].strip())
            context = sanitize(parts[2].strip()) if len(parts) > 2 else ""
            rows.append((source, target, context))
    return rows


def locate(source: str, context: str) -> tuple[Token, list[Token]]:
    """Find ``source`` in ``context`` and return its token plus neighbours."""
    tokens = tokenize(context)
    for i, tok in enumerate(tokens):
        if tok.kind is TokenKind.WORD and tok.text.lower() == source.lower():
            return tok, context_of(tokens, i)
    return Token(source, 0, len(source), TokenKind.WORD), []


def load_training_pairs(
    path: Path, engine: RuleEngine | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    X: list[dict[str, Any]] = []
    y: list[str] = []
    skipped = 0
    for source, target, context in read_training_rows(path):
        label = derive_label_with_rules(source, target, engine)
        if label is None:
            skipped += 1
            log.warning("no edit operation explains %r -> %r; skipped", source, target)
            continue
        tok, ctx = locate(source, context)
        X.append(extract_features(tok, ctx))
        y.append(label)
    if skipped:
        log.warning("skipped %d rows that no operation explains", skipped)
    return X, y


def build_pipeline() -> Any:
    _require_sklearn()
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    return Pipeline(
        [
            ("vec", DictVectorizer(sparse=True)),
            ("clf", LogisticRegression(max_iter=2000, C=2.0, class_weight="balanced")),
        ]
    )


def train(X: Sequence[dict[str, Any]], y: Sequence[str], *, seed: int = 42) -> Any:
    model = build_pipeline()
    model.set_params(clf__random_state=seed)
    model.fit(list(X), list(y))
    return model


def cross_validate(X: Sequence[dict[str, Any]], y: Sequence[str], folds: int = 5) -> CVReport:
    _require_sklearn()
    from collections import Counter

    from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score

    counts = Counter(y)
    min_class = min(counts.values())
    n_splits = max(2, min(folds, len(y)))
    splitter: Any
    if min_class >= n_splits:
        splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    else:
        splitter = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    scores = cross_val_score(build_pipeline(), list(X), list(y), cv=splitter)
    return CVReport(
        folds=n_splits,
        accuracies=tuple(float(s) for s in scores),
        n_samples=len(y),
        label_counts=dict(counts),
    )


def save_model(model: Any, path: Path) -> None:
    _require_sklearn()
    import joblib

    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "version": __version__, "labels": list(LABELS)},
        path,
    )
