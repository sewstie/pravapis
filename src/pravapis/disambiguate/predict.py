"""Inference side of the classifier.

Below ``CONFIDENCE_THRESHOLD`` the disambiguator returns the input unchanged:
silence beats a wrong answer. The model only covers Narkamaŭka → Taraškievica;
the reverse alternations (ля → ла) are lexicon-only.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from pravapis.disambiguate.features import extract_features
from pravapis.disambiguate.labels import KEEP, apply_label
from pravapis.types import Orthography, Token

CONFIDENCE_THRESHOLD: Final[float] = 0.75


class Disambiguator:
    direction: Final[Orthography] = Orthography.TARASKIEVICA

    def __init__(
        self,
        model: Any,
        *,
        threshold: float = CONFIDENCE_THRESHOLD,
        version: str = "unknown",
    ):
        self._model = model
        self.threshold = threshold
        self.version = version
        self._classes: list[str] = [str(c) for c in model.classes_]

    @classmethod
    def load(cls, path: Path, *, threshold: float = CONFIDENCE_THRESHOLD) -> Disambiguator:
        try:
            import joblib
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("install pravapis[ml] to load the disambiguation model") from exc
        payload = joblib.load(path)
        if isinstance(payload, dict) and "model" in payload:
            return cls(payload["model"], threshold=threshold, version=str(payload.get("version")))
        return cls(payload, threshold=threshold)

    def is_confident(self, score: float) -> bool:
        return score >= self.threshold

    def predict_label(self, token: Token, context: Sequence[Token]) -> tuple[str, float]:
        return self.predict_labels_batch([(token, list(context))])[0]

    def predict_labels_batch(
        self, items: Sequence[tuple[Token, list[Token]]]
    ) -> list[tuple[str, float]]:
        if not items:
            return []
        feats = [extract_features(tok, ctx) for tok, ctx in items]
        probs = self._model.predict_proba(feats)
        out: list[tuple[str, float]] = []
        for row in probs:
            best = max(range(len(row)), key=lambda i: row[i])
            out.append((self._classes[best], float(row[best])))
        return out

    def predict(self, token: Token, context: Sequence[Token]) -> tuple[str, float]:
        """Return (converted lowercase word, confidence).

        Unconfident predictions collapse to the input word so the caller can
        treat them as "no opinion".
        """
        return self.predict_batch([(token, list(context))])[0]

    def predict_batch(self, items: Sequence[tuple[Token, list[Token]]]) -> list[tuple[str, float]]:
        results: list[tuple[str, float]] = []
        for (tok, _), (label, score) in zip(items, self.predict_labels_batch(items), strict=True):
            word = tok.text.lower()
            if label == KEEP or not self.is_confident(score):
                results.append((word, score))
            else:
                results.append((apply_label(word, label), score))
        return results
