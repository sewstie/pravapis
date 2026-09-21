"""What the converter is contracted to do, and how to tell whether a difference is in it.

A diff between the be and be-tarask wikis is evidence that two writers wrote something
differently. It is not yet evidence that the converter should have changed anything.
This module draws that line, and it draws it in one place so that the recall headline,
the corpus aligner and the documentation cannot disagree about where it falls.

## The neutral fold

:func:`neutral_fold` erases exactly the alternations the converter is contracted to
make — assimilative ь, э/е, ё/о, і/ы, soft л, ґ/г, ў/у — and nothing else. Two forms
that fold to the same string differ only in ways the converter is supposed to handle.

It is used for two things, and the second is the important one:

1. **Bucketing.** ``fold(n) == fold(t)`` is a far better test of "same word, different
   spelling" than character similarity, which cannot tell `снег`/`сьнег` (one edit,
   in scope) from `Шапена`/`Шапэна` (one edit, in scope) from `гены`/`гэны` (one edit,
   different word).

2. **Aligning the corpus without biasing it.** Sentence pairs are kept on similarity,
   and raw similarity punishes exactly the sentences worth keeping: the more
   orthographic changes a sentence carries, the less similar its two versions look, so
   a raw-similarity filter systematically drops the sentences with the most work in
   them. Folding both sides first removes that gradient — a sentence with fifteen
   softness marks scores the same as one with none.

   The fold is deliberately **not** "run the converter and compare". That would keep
   the sentences the converter already handles and drop the ones it does not, which is
   the same bias pointing the other way and much harder to notice.

## The four buckets

``in_scope``            differs only by modelled alternations. **This is the headline.**
``grammatical``         differs by a case or form ending. Out of scope by the
                        codification's own scope: Збор 2005 is a spelling code
                        (§1–92, "даведнік цяжкасьцяў беларускага правапісу") and does
                        not legislate declension at all.
``reference_deviates``  the be-tarask side contradicts a § of the 2005 code, so the
                        converter is right not to reproduce it. Cited per pattern.
``not_orthographic``    the two writers chose different words.

Only ``in_scope`` counts for or against the headline recall. The other three are
reported with their counts, because an exclusion nobody can see is indistinguishable
from a filter that was tuned until the number looked good.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum
from typing import Final

import regex


class Scope(StrEnum):
    IN_SCOPE = "in_scope"
    GRAMMATICAL = "grammatical"
    REFERENCE_DEVIATES = "reference_deviates"
    NOT_ORTHOGRAPHIC = "not_orthographic"


#: Single-character folds. Each erases one alternation the converter is contracted to
#: make, in both directions, by mapping both spellings onto one representative.
_FOLD_MAP: Final[dict[str, str]] = {
    "ь": "",  # assimilative softness (сьнег → снег)
    "э": "е",  # loan э (сэзон → сезон)
    "ё": "о",  # includes the soft-л ё (блёк → блок)
    "ы": "і",  # loan ы (сыстэма → сістэма)
    "ґ": "г",  # ґ is optional and alphabetised as г
    "ў": "у",  # ў/у is positional and both codes agree on it
}

#: After л, these vowels carry the softness instead of a ь, so they fold too.
_AFTER_L: Final[dict[str, str]] = {"я": "а", "ю": "у"}

_WORD_TAIL: Final[regex.Pattern[str]] = regex.compile(r"[\p{Cyrillic}’ʼ'-]+$")


def neutral_fold(word: str) -> str:
    """Erase every alternation the converter is contracted to make, and nothing else.

    Lossy on purpose: it is an equality test for "same word, different spelling", not a
    normalisation anybody should store. ``гены`` and ``гэны`` fold together too — that
    is the cost of a fold that cannot look at etymology, and it makes the in-scope
    bucket slightly generous rather than slightly strict.
    """
    out: list[str] = []
    previous = ""
    for char in word.lower():
        if previous == "л" and char in _AFTER_L:
            folded = _AFTER_L[char]
        else:
            folded = _FOLD_MAP.get(char, char)
        out.append(folded)
        previous = char
    return "".join(out)


def fold_similarity(a: str, b: str) -> float:
    """Character similarity of two strings *after* folding, so orthography costs nothing."""
    return SequenceMatcher(None, neutral_fold(a), neutral_fold(b), autojunk=False).ratio()


# --- declared out-of-scope patterns ----------------------------------------------------
@dataclass(frozen=True, slots=True)
class Pattern:
    """One declared reason a difference is not the converter's to make."""

    label: str
    scope: Scope
    citation: str
    #: (source suffix, target suffix) pairs this covers, written in ordinary spelling
    #: and folded on construction — the comparison happens on folded strings, so an
    #: unfolded table would silently never match (``аў`` folds to ``ау``).
    endings: tuple[tuple[str, str], ...] = ()
    #: or a regex over the folded (source, target) joined as "source>target"
    matches: regex.Pattern[str] | None = None

    @property
    def folded_endings(self) -> tuple[tuple[str, str], ...]:
        return tuple((neutral_fold(a), neutral_fold(b)) for a, b in self.endings)


#: Case and form endings. The 2005 code does not legislate these, so a difference in one
#: is not a spelling difference and the converter is not contracted to make it.
#:
#: The citation is the *scope* of the code rather than a section inside it, which is the
#: honest form here: there is no § to cite because the subject is absent. Збор правілаў
#: 2005 runs §1–92 and its preface calls it "даведнік цяжкасьцяў беларускага правапісу";
#: every section is orthographic. Declension belongs to a grammar, not to it.
_NOT_LEGISLATED: Final[str] = "Збор 2005 §1–92 is a spelling code; declension is outside it"

GRAMMATICAL_PATTERNS: Final[tuple[Pattern, ...]] = (
    Pattern(
        "genitive singular -а / -у",
        Scope.GRAMMATICAL,
        _NOT_LEGISLATED,
        endings=(("а", "у"), ("у", "а")),
    ),
    Pattern(
        "genitive plural -аў / -яў",
        Scope.GRAMMATICAL,
        _NOT_LEGISLATED,
        endings=(("", "аў"), ("", "яў"), ("аў", ""), ("яў", ""), ("а", "аў"), ("у", "аў")),
    ),
    Pattern(
        "possessive pronoun form (яго / ягонага)",
        Scope.GRAMMATICAL,
        _NOT_LEGISLATED,
        matches=regex.compile(r"^(яго|іх|яе)>(ягон|іхн|ейн)"),
    ),
)

#: Spellings where the be-tarask side contradicts the 2005 code. The converter is right
#: not to reproduce these, so counting them against it would be measuring the reference.
REFERENCE_PATTERNS: Final[tuple[Pattern, ...]] = (
    Pattern(
        "-эйск- for -ейск-",
        Scope.REFERENCE_DEVIATES,
        "Збор 2005, §11б заўвага — the adjective suffix -ейск- keeps е after a hard "
        "consonant, so эўрапэйскі is an error and not a variant",
        matches=regex.compile(r"ейск.*>.*эйск"),
    ),
)

_MIN_STEM: Final[int] = 3
_MAX_ENDING: Final[int] = 3


def _ending_change(a: str, b: str) -> tuple[str, str] | None:
    """``(old suffix, new suffix)`` when two words share a stem and differ only at the end."""
    common = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        common += 1
    if common < _MIN_STEM:
        return None
    old, new = a[common:], b[common:]
    if len(old) > _MAX_ENDING or len(new) > _MAX_ENDING:
        return None
    return old, new


def classify_scope(source: str, expected: str) -> tuple[Scope, str]:
    """Which bucket a difference falls in, and why.

    Order matters: in-scope is tested first, so a pair that differs *only* by modelled
    alternations is never diverted into an exclusion bucket by a pattern that also
    happens to match it.
    """
    folded_source, folded_expected = neutral_fold(source), neutral_fold(expected)
    if folded_source == folded_expected:
        return Scope.IN_SCOPE, "differs only by alternations the converter models"

    joined = f"{folded_source}>{folded_expected}"
    ending = _ending_change(folded_source, folded_expected)
    for pattern in (*REFERENCE_PATTERNS, *GRAMMATICAL_PATTERNS):
        if pattern.matches is not None and pattern.matches.search(joined):
            return pattern.scope, f"{pattern.label} — {pattern.citation}"
        if ending is not None and ending in pattern.folded_endings:
            return pattern.scope, f"{pattern.label} — {pattern.citation}"
    return Scope.NOT_ORTHOGRAPHIC, "the two writers chose different words"


# --- intervals -------------------------------------------------------------------------
def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Used on every per-class recall number because the classes are small: a bare "29.5%"
    over a hundred cases and a "29.5%" over ten thousand are not the same claim, and
    only one of them supports a decision about where to spend the next week.

    Wilson rather than the normal approximation because the classes are small *and* the
    proportions are near the ends, where the normal interval runs past 0 and 1 and stops
    meaning anything.
    """
    if total <= 0:
        return (0.0, 0.0)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def format_interval(successes: int, total: int) -> str:
    """``29.5% [21, 39]`` — the number and what it is worth."""
    if total <= 0:
        return "—"
    low, high = wilson(successes, total)
    return f"{successes / total:.1%} [{low:.0%}, {high:.0%}]"
