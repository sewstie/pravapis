"""Transliteration between Cyrillic and the Latin scripts used for Belarusian.

Script is a separate axis from orthography. ``Orthography`` picks a spelling
(Narkamaŭka or Taraškievica); ``Script`` picks a writing system (Cyrillic, Łacinka,
or the 2007 national romanisation). The two compose.

They are not, however, independent in practice. **Łacinka marks assimilative softness
exactly as Taraškievica does** — сьнег → śnieh — while the 2007 romanisation marks
only the ь that is written, as Narkamaŭka does — снег → snieh. Each Latin scheme
therefore shares a softness convention with one orthography, recorded in
:data:`PAIRED`. :func:`render` converts to the paired orthography first so that a
Łacinka reader gets śnieh rather than snieh; ``convert=False`` transliterates the
input exactly as given.

The transducer itself (:mod:`pravapis.translit.engine`) knows nothing about any of
this. It is a pure character-level pass, and the orthography step lives here.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

from pravapis.config import find_data_dir
from pravapis.normalize import sanitize
from pravapis.tokenize import tokenize
from pravapis.translit.engine import (
    Scheme,
    SchemeError,
    TransliterationResult,
    load_scheme,
    transliterate_token,
    validate_scheme,
)
from pravapis.types import Orthography, Script, TokenKind

__all__ = [
    "LACINKA_ONLY",
    "OFFICIAL_ONLY",
    "PAIRED",
    "Scheme",
    "SchemeError",
    "ScriptDetection",
    "TransliterationResult",
    "Transliterator",
    "detect_script",
    "load_scheme",
    "reverse_scheme_name",
    "scheme_path",
    "validate_scheme",
]

#: The orthography each Latin scheme shares a softness convention with.
PAIRED: Final[dict[Script, Orthography]] = {
    Script.LACINKA: Orthography.TARASKIEVICA,
    Script.OFFICIAL: Orthography.NARKAMAUKA,
}

#: Scripts pravapis can read back into Cyrillic. The 2007 romanisation is absent on
#: purpose: it does not write assimilative softness, so the reverse cannot be faithful.
REVERSIBLE: Final[frozenset[Script]] = frozenset({Script.LACINKA})

_SCHEME_FILES: Final[dict[Script, str]] = {
    Script.LACINKA: "lacinka",
    Script.OFFICIAL: "official2007",
}


def scheme_path(script: Script, *, reverse: bool = False, data_dir: Path | None = None) -> Path:
    """Where the YAML table for ``script`` lives."""
    if script is Script.CYRILLIC:
        raise SchemeError("Cyrillic is the source script, not a transliteration scheme")
    base = (data_dir or find_data_dir()) / "translit"
    name = _SCHEME_FILES[script]
    return base / f"{name}_reverse.yaml" if reverse else base / f"{name}.yaml"


def reverse_scheme_name(script: Script) -> str:
    return f"{_SCHEME_FILES[script]}_reverse"


@lru_cache(maxsize=8)
def _load(path_str: str) -> Scheme:
    return load_scheme(Path(path_str))


class Transliterator:
    """One scheme, one direction, applied to whole texts.

    Only word tokens are transliterated. Numbers, punctuation and whitespace are
    reproduced byte-for-byte, which keeps ``tokenize``'s losslessness meaningful for
    everything the scheme does not claim to convert.
    """

    def __init__(self, scheme: Scheme):
        self.scheme = scheme

    @classmethod
    def load(
        cls, script: Script, *, reverse: bool = False, data_dir: Path | None = None
    ) -> Transliterator:
        if reverse and script not in REVERSIBLE:
            raise SchemeError(
                f"{script.value} is forward-only: it does not write assimilative softness, "
                "so a reverse table could not round-trip"
            )
        return cls(_load(str(scheme_path(script, reverse=reverse, data_dir=data_dir))))

    def word(self, word: str) -> TransliterationResult:
        return transliterate_token(self.scheme, word)

    def transliterate(self, text: str) -> TransliterationResult:
        out: list[str] = []
        unresolved: list[str] = []
        for token in tokenize(text):
            if token.kind in (TokenKind.WORD, TokenKind.LATIN):
                result = transliterate_token(self.scheme, token.text)
                out.append(result.text)
                for ch in result.unresolved:
                    if ch not in unresolved:
                        unresolved.append(ch)
            else:
                out.append(token.text)
        return TransliterationResult("".join(out), tuple(unresolved))


def transliterate(text: str, script: Script, *, reverse: bool = False) -> str:
    """Script conversion only — no orthography step. See :func:`render` for that."""
    source_script = script if reverse else Script.CYRILLIC
    return (
        Transliterator.load(script, reverse=reverse)
        .transliterate(sanitize(text, source_script))
        .text
    )


# --- detection ---------------------------------------------------------------------------
#: Letters only Łacinka writes. Hard л is frequent in running Belarusian, so ł shows up in
#: any real Łacinka sentence; the 2007 scheme spells the same sound plain l.
LACINKA_ONLY: Final[frozenset[str]] = frozenset("łŁ")
#: Letters only the 2007 scheme writes: ль is ĺ there and plain l in Łacinka.
OFFICIAL_ONLY: Final[frozenset[str]] = frozenset("ĺĹ")


@dataclass(frozen=True, slots=True)
class ScriptDetection:
    """What script a text is in, and whether the evidence actually settled it."""

    script: Script | None
    certain: bool
    reason: str

    def __bool__(self) -> bool:
        return self.script is not None


def detect_script(text: str) -> ScriptDetection:
    """Guess the script of ``text``, saying plainly when it could not be settled.

    Cyrillic is decided by the alphabet. The two Latin schemes share most of their
    letters — š, č, ž, ŭ, ś, ź, ć, ń and the digraphs — and differ in exactly one place
    that shows up often: Łacinka writes hard л as ``ł`` and soft ль as ``l``, while the
    2007 scheme writes ``l`` and ``ĺ``. So ``ł`` means Łacinka and ``ĺ`` means official.

    A Latin text with neither is genuinely ambiguous — usually because it is too short to
    contain an л at all — and this says so rather than picking one. Guessing the scheme
    wrong silently corrupts every soft l in the output.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return ScriptDetection(None, False, "no letters")
    cyrillic = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    if cyrillic > len(letters) / 2:
        return ScriptDetection(Script.CYRILLIC, True, f"{cyrillic}/{len(letters)} Cyrillic")
    found = set(text)
    has_lacinka, has_official = found & LACINKA_ONLY, found & OFFICIAL_ONLY
    if has_lacinka and has_official:
        # ł belongs to Łacinka and ĺ to the 2007 scheme; no single scheme writes both,
        # so this is mixed or mis-typed and picking either would corrupt half of it.
        return ScriptDetection(None, False, "contains both ł and ĺ — no scheme writes both")
    if has_lacinka:
        return ScriptDetection(Script.LACINKA, True, "contains ł, which only Łacinka writes")
    if has_official:
        return ScriptDetection(
            Script.OFFICIAL, True, "contains ĺ, which only the 2007 scheme writes"
        )
    return ScriptDetection(
        Script.LACINKA,
        False,
        "Latin, but no ł or ĺ to tell the two schemes apart — too short, or it has no л",
    )
