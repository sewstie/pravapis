"""Edit-operation labels for the classifier.

The classifier does not predict target *words* — that would never generalise
past the training vocabulary. It predicts which lexically-conditioned
alternation applies to a word (soften its л? turn сі into сы? keep it?), and
``apply_label`` performs the edit. Rules then finish the job (тр → тар etc.).
"""

from __future__ import annotations

from typing import Final

import regex

KEEP: Final[str] = "keep"
SOFT_L: Final[str] = "soft_l"
I_TO_Y: Final[str] = "i_to_y"
E_TO_E: Final[str] = "e_to_e"
PARTICLE: Final[str] = "particle"

LABELS: Final[tuple[str, ...]] = (KEEP, SOFT_L, I_TO_Y, E_TO_E, PARTICLE)

_SOFT_VOWEL: Final[dict[str, str]] = {"а": "я", "о": "ё", "у": "ю"}
_L_VOWEL_RE: Final[regex.Pattern[str]] = regex.compile(r"л([аоу])")
_L_CONS_RE: Final[regex.Pattern[str]] = regex.compile(r"л(?=[бвгдзкмнпрстфхцчшж]|$)")
_I_RE: Final[regex.Pattern[str]] = regex.compile(r"(?<=[сз])і")
_E_RE: Final[regex.Pattern[str]] = regex.compile(r"(?<=[бвгдзмнпрстфх])е")
_PARTICLES: Final[dict[str, str]] = {"не": "ня", "без": "бяз"}


def apply_label(word: str, label: str) -> str:
    """Apply one edit operation to a lowercase word."""
    match label:
        case "keep":
            return word
        case "soft_l":
            new = _L_VOWEL_RE.sub(lambda m: "л" + _SOFT_VOWEL[m.group(1)], word, count=1)
            if new != word:
                return new
            return _L_CONS_RE.sub("ль", word, count=1)
        case "i_to_y":
            return _I_RE.sub("ы", word, count=1)
        case "e_to_e":
            return _E_RE.sub("э", word, count=1)
        case "particle":
            return _PARTICLES.get(word, word)
        case _:
            raise ValueError(f"unknown label {label!r}")


def derive_label(source: str, target: str) -> str | None:
    """Which single operation turns ``source`` into ``target``? None if none does.

    ``target`` is compared *before* the deterministic rules run, so callers
    should strip rule effects first (see ``train.load_training_pairs``).
    """
    source, target = source.lower(), target.lower()
    if source == target:
        return KEEP
    for label in LABELS[1:]:
        if apply_label(source, label) == target:
            return label
    return None
