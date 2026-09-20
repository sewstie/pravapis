"""Converter configuration: where the data lives and how cautious the model is."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Final

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

ENV_DATA_DIR: Final[str] = "PRAVAPIS_DATA_DIR"

#: Words matching any of these (lowercase) patterns are handed to the classifier
#: when neither the lexicon nor the rules changed them. They mark the alternations
#: that are lexically, not phonologically, conditioned.
DEFAULT_AMBIGUITY_TRIGGERS: Final[tuple[str, ...]] = (
    r"^(не|без)$",  # ня / бяз depends on the next word's stress
    r"[бвгдзкмпстфх]л[аоу]",  # hard л after a consonant: план/плян vs лапа
    r"^л[аоу]",  # word-initial hard л: логіка/лёгіка vs лапа
    r"[сз]і",  # сістэма/сыстэма vs сіла
    r"[дтнмсзпбвфр]е",  # loan е vs э: метр/мэтар vs мера
)

RULE_FILES: Final[tuple[str, ...]] = (
    "palatalization.yaml",
    "loanwords.yaml",
    "morphology.yaml",
)


def find_data_dir() -> Path:
    """``$PRAVAPIS_DATA_DIR``, else the repository ``data/`` next to ``src/``, else ``./data``."""
    env = os.environ.get(ENV_DATA_DIR)
    if env:
        return Path(env)
    candidate = Path(__file__).resolve().parent.parent.parent / "data"
    if candidate.is_dir():
        return candidate
    return Path.cwd() / "data"


class Config(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    lexicon: Path
    #: TSV sources a compiled ``lexicon`` must match (checked on load); None skips the check
    lexicon_sources: Path | None = None
    rules: tuple[Path, ...]
    #: case-dependent substitutions (data/lexicon/case/*.tsv), see pravapis.lexicon.case_forms
    case_forms: Path | None = None
    #: stem etymology inventory (data/lexicon/stems/*.tsv), see pravapis.lexicon.stems
    stems: Path | None = None
    #: directory built by scripts/build_stress_table.py (GrammarDB stress marks)
    stress: Path | None = None
    #: directory built by scripts/build_morphology.py (GrammarDB noun lemmas)
    morphology: Path | None = None
    model: Path | None = None
    confidence_threshold: float = 0.75
    ambiguity_triggers: tuple[str, ...] = DEFAULT_AMBIGUITY_TRIGGERS

    @field_validator("confidence_threshold")
    @classmethod
    def _threshold_in_range(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence_threshold must be within [0, 1]")
        return value

    @classmethod
    def default(cls, data_dir: Path | None = None) -> Config:
        """Lexicon + rules only.

        The classifier is never picked up implicitly, even if a trained model
        sits in ``data/models/``: on the gold set it made results worse (see
        README, "Why the classifier was removed"). Opt in with an explicit
        ``model:`` entry in a config file and ``pip install pravapis[ml]``.
        """
        base = data_dir or find_data_dir()
        compiled = base / "lexicon.marisa"
        lexicon = compiled if compiled.is_file() else base / "lexicon"
        stress = base / "stress"
        return cls(
            lexicon=lexicon,
            lexicon_sources=base / "lexicon" if lexicon == compiled else None,
            case_forms=base / "lexicon" / "case" if (base / "lexicon" / "case").is_dir() else None,
            stems=base / "lexicon" / "stems" if (base / "lexicon" / "stems").is_dir() else None,
            rules=tuple(base / "rules" / name for name in RULE_FILES),
            stress=stress if (stress / "first_stressed.marisa").is_file() else None,
            morphology=(
                base / "morphology"
                if (base / "morphology" / "ment_lemmas.marisa").is_file()
                else None
            ),
            model=None,
        )

    @classmethod
    def load(cls, path: Path) -> Config:
        """Load a YAML/JSON config; relative paths resolve against the config file."""
        with path.open(encoding="utf-8") as fh:
            raw: dict[str, Any] = yaml.safe_load(fh) or {}
        base = path.resolve().parent

        def resolve(p: str) -> Path:
            candidate = Path(p)
            return candidate if candidate.is_absolute() else base / candidate

        if "lexicon" in raw:
            raw["lexicon"] = resolve(str(raw["lexicon"]))
        if "rules" in raw:
            raw["rules"] = tuple(resolve(str(r)) for r in raw["rules"])
        if raw.get("case_forms"):
            raw["case_forms"] = resolve(str(raw["case_forms"]))
        if raw.get("stems"):
            raw["stems"] = resolve(str(raw["stems"]))
        if raw.get("lexicon_sources"):
            raw["lexicon_sources"] = resolve(str(raw["lexicon_sources"]))
        if raw.get("stress"):
            raw["stress"] = resolve(str(raw["stress"]))
        if raw.get("morphology"):
            raw["morphology"] = resolve(str(raw["morphology"]))
        if raw.get("model"):
            raw["model"] = resolve(str(raw["model"]))
        return cls.model_validate(raw)
