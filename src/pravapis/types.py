"""Core value types shared by every layer of pravapis.

Everything here is immutable and slotted: the pipeline allocates one
``Conversion`` per word token, so keeping these tiny matters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypedDict


class Orthography(StrEnum):
    """The two Belarusian orthographies. Used as the *target* of a conversion."""

    NARKAMAUKA = "narkamauka"
    TARASKIEVICA = "taraskievica"

    @property
    def opposite(self) -> Orthography:
        if self is Orthography.NARKAMAUKA:
            return Orthography.TARASKIEVICA
        return Orthography.NARKAMAUKA


class Script(StrEnum):
    """The writing system a text is in.

    Orthogonal to :class:`Orthography`: Narkamaŭka and Taraškievica are two spellings
    of Belarusian, Cyrillic and the Latin schemes are two ways of writing either. Each
    Latin scheme does, however, share a softness convention with one orthography —
    Łacinka marks assimilative softness (śnieh) as Taraškievica does, the 2007 national
    romanisation does not (snieh) as Narkamaŭka does not — which is why
    :data:`pravapis.translit.PAIRED` exists.
    """

    CYRILLIC = "cyrillic"
    LACINKA = "lacinka"
    OFFICIAL = "official"

    @property
    def is_latin(self) -> bool:
        return self is not Script.CYRILLIC


#: The options argument of the public :func:`pravapis.convert`. Written with the
#: functional syntax because ``from`` is a Python keyword and the wire key has to stay
#: ``from`` — the contract is the same in every language, so the language bends, not it.
#: ``to`` is required; ``from`` may be omitted, in which case it is the opposite of ``to``.
ConvertOptions = TypedDict("ConvertOptions", {"from": str, "to": str}, total=False)


class Method(StrEnum):
    """Which stage of the cascade resolved a word."""

    IDENTITY = "identity"  # no change needed
    LEXICON = "lexicon"  # exact dictionary hit
    RULE = "rule"  # deterministic rule fired
    MODEL = "model"  # classifier resolved it
    UNKNOWN = "unknown"  # passed through unchanged


class TokenKind(StrEnum):
    WORD = "word"
    PUNCT = "punct"
    SPACE = "space"
    NUMBER = "number"
    LATIN = "latin"


@dataclass(frozen=True, slots=True)
class Token:
    text: str
    start: int
    end: int
    kind: TokenKind

    def __len__(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class Conversion:
    source: str
    target: str
    method: Method
    rule_id: str | None = None
    confidence: float = 1.0
    #: where ``source`` starts in the *sanitized* input (see :func:`pravapis.sanitize`,
    #: which is idempotent, so a caller can reproduce the string these index into)
    offset: int = -1
    #: why this change is permissible: the citation of the rule that fired, joined with
    #: "; " when several did. ``None`` for a lexicon hit, which is its own evidence.
    citation: str | None = None

    @property
    def changed(self) -> bool:
        return self.source != self.target

    def to_change(self) -> dict[str, Any]:
        """This conversion in the frozen wire shape (see :class:`ConversionResult`)."""
        return {
            "from": self.source,
            "to": self.target,
            "offset": self.offset,
            "rule": self.rule_id,
            "class": self.method.value,
            "citation": self.citation,
        }


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """The result of converting a text, and the frozen public shape of that result.

    :meth:`to_dict` is the contract, identical in every implementation::

        convert(text, {"from": …, "to": …})
          → {"text": …,
             "changes": [{"from", "to", "offset", "rule", "class", "citation"}, …]}

    ``changes`` is always populated — it is not behind a flag. The cascade has to decide
    what happened to every word in order to convert it at all, so reporting those
    decisions costs an attribute read, and making it opt-in only guarantees that the
    explanation and the conversion drift apart. ``explain()`` is a view over this.

    * ``offset`` indexes the **sanitized** input. ``sanitize`` can change a string's
      length (it strips zero-width characters and applies NFC), and it is idempotent,
      so a caller that wants to map offsets back can sanitize its own input and index
      into that.
    * ``class`` is the cascade stage that resolved the word — ``lexicon``, ``rule``,
      ``identity``, ``model`` — which is the kind of evidence behind the change.
    * ``citation`` is where that evidence comes from: the § of the codification the
      rule cites. ``null`` for a lexicon hit, whose evidence is the entry itself.
    """

    text: str
    conversions: tuple[Conversion, ...]
    stats: dict[Method, int]

    @property
    def changes(self) -> tuple[Conversion, ...]:
        """Only the words that actually changed, in document order."""
        return tuple(c for c in self.conversions if c.changed)

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "changes": [c.to_change() for c in self.changes]}


@dataclass(frozen=True, slots=True)
class RuleTrace:
    """One rule firing: what the word looked like before and after."""

    rule_id: str
    before: str
    after: str


@dataclass(frozen=True, slots=True)
class TokenExplanation:
    source: str
    target: str
    method: Method
    rule_id: str | None
    confidence: float
    traces: tuple[RuleTrace, ...] = field(default_factory=tuple)


METHOD_PRIORITY: dict[Method, int] = {
    Method.UNKNOWN: 0,
    Method.IDENTITY: 1,
    Method.LEXICON: 2,
    Method.RULE: 3,
    Method.MODEL: 4,
}
