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

    @property
    def code(self) -> str:
        """The wire spelling of the *direction*, as opposed to the target orthography.

        ``Orthography`` names where a conversion is going; the response contract names
        the journey. They are not interchangeable on the wire: ``"taraskievica"`` says
        nothing about where the text started, and a reader of the JSON has to know the
        direction to interpret ``from``/``to`` at all.
        """
        return "n2t" if self is Orthography.TARASKIEVICA else "t2n"

    @classmethod
    def from_code(cls, code: str) -> Orthography:
        """The target orthography for a wire direction code."""
        if code == "n2t":
            return cls.TARASKIEVICA
        if code == "t2n":
            return cls.NARKAMAUKA
        raise ValueError(f"direction must be 'n2t' or 't2n', got {code!r}")


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
class ChangeContext:
    """Why a *cross-word* rule fired: what it looked at outside the word itself.

    Populated only for rules that read a neighbouring word — §18's У → Ў after a vowel,
    §13's і → й, and the clitics. A word-internal rule has ``context: null``, and that
    absence is meaningful: it says the change is reproducible from the word alone.
    """

    #: what the rule consulted: ``prev_word_vowel``, ``prev_word`` or ``next_word``
    trigger: str
    #: the non-space characters the rule reached across, when it reached across any.
    #: §18 Заўвага makes a hyphen or a quotation mark transparent, so *школу «Ўітні»*
    #: is a rule firing over a «, and a reader who cannot see that cannot check it.
    across: str | None = None
    #: the § the trigger itself rests on, when the codification numbers it separately
    #: from the rule's own citation
    rule: str | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"trigger": self.trigger}
        if self.across is not None:
            out["across"] = self.across
        if self.rule is not None:
            out["rule"] = self.rule
        return out


@dataclass(frozen=True, slots=True)
class Conversion:
    source: str
    target: str
    method: Method
    rule_id: str | None = None
    confidence: float = 1.0
    #: where ``target`` starts in the **output** text, counted in Unicode code points.
    #: See :class:`ConversionResult` for why the output and why code points.
    start: int = -1
    #: one past the last code point of ``target`` in the output text
    end: int = -1
    #: why this change is permissible: the citation of the rule that fired, joined with
    #: "; " when several did. ``None`` for a lexicon hit, which is its own evidence.
    citation: str | None = None
    #: set only for cross-word rules; see :class:`ChangeContext`
    context: ChangeContext | None = None

    @property
    def changed(self) -> bool:
        return self.source != self.target

    def to_change(self) -> dict[str, Any]:
        """This conversion in the frozen wire shape (see :class:`ConversionResult`)."""
        return {
            "start": self.start,
            "end": self.end,
            "from": self.source,
            "to": self.target,
            "stage": self.method.value,
            "rule": self.rule_id,
            "citation": self.citation,
            "context": None if self.context is None else self.context.to_json(),
        }


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """The result of converting a text, and the frozen public shape of that result.

    :meth:`to_dict` **is** the contract. Every conversion endpoint in every
    implementation returns exactly this, documented in ``docs/API.md``::

        {"text": …, "direction": "n2t" | "t2n",
         "engine_version": …, "data_version": …,
         "changes": [{"start", "end", "from", "to",
                      "stage", "rule", "citation", "context"}, …],
         "unresolved": [...]}

    ``changes`` is always populated — it is not behind a flag. The cascade has to decide
    what happened to every word in order to convert it at all, so reporting those
    decisions costs an attribute read, and making it opt-in only guarantees that the
    explanation and the conversion drift apart. ``explain()`` is a view over this.

    Four decisions here are load-bearing, and each is a parity bug if a port guesses:

    * ``start``/``end`` index the **output** text, in **Unicode code points**. The
      output, because that is the string a caller displays and wants to highlight; the
      input offsets are not recoverable from it once a rule changes a word's length.
      Code points, because Python indexes strings that way and JavaScript does not —
      they agree on Cyrillic and part company on the first emoji, so a JS port converts
      to UTF-16 units at its own boundary rather than pretending the difference is not
      there.
    * **Sanitizer effects are not changes.** ``sanitize`` folds homoglyphs, normalises
      apostrophes and strips zero-width characters at the input boundary. Those edits
      are real but they are hygiene, not orthography, and reporting them would bury the
      handful of actual conversions under one entry per curly quote.
    * ``context`` is set only for cross-word rules, so ``null`` positively means the
      change is reproducible from the word alone.
    * ``stage`` is the cascade stage that resolved the word — ``lexicon``, ``rule``,
      ``identity``, ``model`` — which is the kind of evidence behind the change, and
      ``citation`` is where that evidence comes from: the § of the codification the rule
      cites. ``null`` for a lexicon hit, whose evidence is the entry itself.
    """

    text: str
    conversions: tuple[Conversion, ...]
    stats: dict[Method, int]
    #: the target orthography; serialised as its :attr:`Orthography.code`
    direction: Orthography = Orthography.TARASKIEVICA
    #: words the converter saw a decision in and declined to make: they matched an
    #: ambiguity trigger and no stage of the cascade resolved them, so they were passed
    #: through unchanged. Silence is the right answer there, but a silent silence is
    #: indistinguishable from "nothing to do", so it is reported.
    unresolved: tuple[str, ...] = ()

    @property
    def changes(self) -> tuple[Conversion, ...]:
        """Only the words that actually changed, in document order."""
        return tuple(c for c in self.conversions if c.changed)

    def to_dict(
        self, *, engine_version: str | None = None, data_version: str | None = None
    ) -> dict[str, Any]:
        """The frozen wire shape. Versions are resolved from the build when omitted."""
        if engine_version is None:
            from pravapis import __version__

            engine_version = __version__
        if data_version is None:
            from pravapis.dataversion import read_data_version

            data_version = read_data_version()
        return {
            "text": self.text,
            "direction": self.direction.code,
            "engine_version": engine_version,
            "data_version": data_version,
            "changes": [c.to_change() for c in self.changes],
            "unresolved": list(self.unresolved),
        }


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
