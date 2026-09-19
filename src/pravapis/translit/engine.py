"""A context-sensitive, longest-match transducer.

Transliteration is not orthography conversion: there is no cascade, no lexicon and
no competing sources of truth. It is a single left-to-right pass in which, at each
position, the longest grapheme in the scheme's table whose context condition holds is
emitted and consumed.

That single-pass discipline is the point. A rule engine that applied every rule in
priority order and re-ran to a fixpoint — which is what :mod:`pravapis.rules.engine`
correctly does for orthography — would let ``дз → dz`` be re-entered by ``з → z``.
Here ``дз`` is consumed whole and the scan moves past it.

Context conditions are a small closed vocabulary rather than arbitrary regex, so a
scheme file stays readable by someone checking it against a published table:

``initial``            start of the word
``final``              nothing follows
``after_vowel``        previous source character is a vowel (ў counts)
``after_consonant``    previous source character is a consonant
``after_apostrophe``   previous source character is an apostrophe
``after_soft_sign``    previous source character is ь
``after_l``            previous source character is л
``before_vowel``       next source character is a vowel
``before_soft_vowel``  next source character is one of е ё і ю я
``before_consonant``   next source character is a consonant
``default``            always true; the fallback

Conditions are evaluated against the **source** string, never the output, so a rule
can never see a decision another rule already made.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

from pravapis.casing import recase

#: Belarusian vowels, both orthographies.
VOWELS: Final[frozenset[str]] = frozenset("аеёіоуыэюя")
#: ў is a glide: it patterns as a vowel for the purpose of iotation (маўзэр → maŭzer).
GLIDES: Final[frozenset[str]] = frozenset("ў")
SOFT_VOWELS: Final[frozenset[str]] = frozenset("еёіюя")
APOSTROPHES: Final[frozenset[str]] = frozenset("’'ʼ`‘")
SOFT_SIGN: Final[str] = "ь"


class SchemeError(ValueError):
    """A transliteration scheme file is malformed."""


def _is_vowel(ch: str) -> bool:
    return ch in VOWELS or ch in GLIDES


def _is_consonant(ch: str) -> bool:
    return bool(ch) and ch.isalpha() and not _is_vowel(ch) and ch not in {SOFT_SIGN, "ъ"}


#: name -> predicate(source, start, end). ``start``/``end`` bound the matched grapheme.
CONDITIONS: Final[dict[str, Callable[[str, int, int], bool]]] = {
    "default": lambda s, i, j: True,
    "initial": lambda s, i, j: i == 0,
    "final": lambda s, i, j: j >= len(s),
    "after_vowel": lambda s, i, j: i > 0 and _is_vowel(s[i - 1]),
    "after_consonant": lambda s, i, j: i > 0 and _is_consonant(s[i - 1]),
    "after_apostrophe": lambda s, i, j: i > 0 and s[i - 1] in APOSTROPHES,
    "after_soft_sign": lambda s, i, j: i > 0 and s[i - 1] == SOFT_SIGN,
    "after_l": lambda s, i, j: i > 0 and s[i - 1] == "л",
    "before_vowel": lambda s, i, j: j < len(s) and _is_vowel(s[j]),
    "before_soft_vowel": lambda s, i, j: j < len(s) and s[j] in SOFT_VOWELS,
    "before_consonant": lambda s, i, j: j < len(s) and _is_consonant(s[j]),
}


@dataclass(frozen=True, slots=True)
class Mapping:
    """One grapheme, one output, one condition."""

    source: str
    target: str
    when: tuple[str, ...] = ("default",)
    #: the scheme has no faithful rendering for this grapheme — the output is a
    #: best effort and the caller is told. A bare ь is the case in point: Łacinka
    #: writes softness on the consonant (ś, ć, ń), so a ь after one that has no soft
    #: Latin counterpart has nowhere to go.
    lossy: bool = False

    def holds(self, text: str, start: int, end: int) -> bool:
        return any(CONDITIONS[c](text, start, end) for c in self.when)


@dataclass(frozen=True, slots=True)
class SchemeTest:
    input: str
    expected: str


@dataclass(frozen=True)
class Scheme:
    """A named transliteration table, one direction."""

    name: str
    source_label: str
    mappings: tuple[Mapping, ...]
    tests: tuple[SchemeTest, ...] = ()
    description: str = ""
    #: longest source grapheme, so the scan knows how far to look
    _max_len: int = field(default=1, compare=False)
    _by_source: dict[str, tuple[Mapping, ...]] = field(default_factory=dict, compare=False)

    @classmethod
    def build(
        cls,
        name: str,
        source_label: str,
        mappings: Iterable[Mapping],
        tests: Iterable[SchemeTest] = (),
        description: str = "",
    ) -> Scheme:
        ms = tuple(mappings)
        by_source: dict[str, list[Mapping]] = {}
        for m in ms:
            by_source.setdefault(m.source, []).append(m)
        return cls(
            name=name,
            source_label=source_label,
            mappings=ms,
            tests=tuple(tests),
            description=description,
            _max_len=max((len(m.source) for m in ms), default=1),
            _by_source={k: tuple(v) for k, v in by_source.items()},
        )

    def lookup(self, text: str, start: int) -> tuple[str, int, bool] | None:
        """The longest grapheme at ``start`` whose condition holds.

        Returns ``(output, consumed, lossy)``.
        """
        for length in range(min(self._max_len, len(text) - start), 0, -1):
            end = start + length
            for mapping in self._by_source.get(text[start:end], ()):
                if mapping.holds(text, start, end):
                    return mapping.target, length, mapping.lossy
        return None


@dataclass(frozen=True, slots=True)
class TransliterationResult:
    text: str
    #: graphemes the scheme could not render faithfully — either no mapping covered
    #: them at all, or the mapping is marked ``lossy``. In order of first appearance.
    unresolved: tuple[str, ...] = ()


def transliterate_word(scheme: Scheme, word: str) -> TransliterationResult:
    """One word, lowercased in, capitalisation re-applied by the caller."""
    out: list[str] = []
    unresolved: list[str] = []
    i = 0
    while i < len(word):
        hit = scheme.lookup(word, i)
        if hit is None:
            ch = word[i]
            if ch not in unresolved:
                unresolved.append(ch)
            out.append(ch)
            i += 1
            continue
        target, consumed, lossy = hit
        out.append(target)
        if lossy:
            grapheme = word[i : i + consumed]
            if grapheme not in unresolved:
                unresolved.append(grapheme)
        i += consumed
    return TransliterationResult("".join(out), tuple(unresolved))


def transliterate_token(scheme: Scheme, word: str) -> TransliterationResult:
    """A word with its capitalisation restored.

    ``recase`` handles the multi-character expansions correctly: ``Я`` is a single
    letter, which :func:`pravapis.casing.detect_case` reports as *title*, so it comes
    back as ``Ja`` rather than ``JA``.
    """
    result = transliterate_word(scheme, word.lower())
    return TransliterationResult(recase(word, result.text), result.unresolved)


# --- loading -----------------------------------------------------------------------------
def _parse_mapping(raw: dict[str, Any], index: int, path: Path) -> Mapping:
    try:
        source = str(raw["from"])
        target = str(raw["to"])
    except KeyError as exc:
        raise SchemeError(f"{path}: mapping #{index} needs 'from' and 'to'") from exc
    when_raw = raw.get("when", "default")
    when = tuple(w.strip() for w in str(when_raw).split("|") if w.strip())
    unknown = [w for w in when if w not in CONDITIONS]
    if unknown:
        raise SchemeError(
            f"{path}: mapping #{index} ({source!r}) has unknown condition(s) {unknown}; "
            f"known: {sorted(CONDITIONS)}"
        )
    if not source:
        raise SchemeError(f"{path}: mapping #{index} has an empty 'from'")
    return Mapping(source=source, target=target, when=when, lossy=bool(raw.get("lossy", False)))


def load_scheme(path: Path) -> Scheme:
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict):
        raise SchemeError(f"{path}: expected a mapping at top level")
    try:
        name = str(doc["scheme"])
    except KeyError as exc:
        raise SchemeError(f"{path}: no 'scheme' name") from exc
    raw_mappings = doc.get("mappings") or []
    if not raw_mappings:
        raise SchemeError(f"{path}: scheme {name!r} has no mappings")
    mappings = [_parse_mapping(m, i, path) for i, m in enumerate(raw_mappings)]
    tests = [SchemeTest(str(t["input"]), str(t["expected"])) for t in (doc.get("tests") or [])]
    return Scheme.build(
        name=name,
        source_label=str(doc.get("source", "")),
        mappings=mappings,
        tests=tests,
        description=str(doc.get("description", "")),
    )


def validate_scheme(scheme: Scheme, alphabet: Sequence[str]) -> list[str]:
    """Letters of ``alphabet`` that no mapping can consume — the scheme's blind spots."""
    missing: list[str] = []
    for letter in alphabet:
        if scheme.lookup(letter, 0) is None:
            missing.append(letter)
    return missing
