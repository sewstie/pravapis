"""Core value types shared by every layer of belnorm.

Everything here is immutable and slotted: the pipeline allocates one
``Conversion`` per word token, so keeping these tiny matters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Orthography(StrEnum):
    """The two Belarusian orthographies. Used as the *target* of a conversion."""

    NARKAMAUKA = "narkamauka"
    TARASKIEVICA = "taraskievica"

    @property
    def opposite(self) -> Orthography:
        if self is Orthography.NARKAMAUKA:
            return Orthography.TARASKIEVICA
        return Orthography.NARKAMAUKA


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

    @property
    def changed(self) -> bool:
        return self.source != self.target


@dataclass(frozen=True, slots=True)
class ConversionResult:
    text: str
    conversions: tuple[Conversion, ...]
    stats: dict[Method, int]


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
