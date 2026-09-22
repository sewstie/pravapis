"""Request/response models for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from pravapis.types import Method, Orthography, Script

MAX_TEXT_LENGTH = 50_000
MAX_BATCH = 100


class ConvertRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(max_length=MAX_TEXT_LENGTH)
    direction: Orthography
    explain: bool = False


class TransliterateRequest(BaseModel):
    """Script conversion. ``script`` is the target; ``from_script`` reads Latin back.

    ``convert`` controls the orthography step: Łacinka is paired with Taraškievica and
    the 2007 romanisation with Narkamaŭka, so by default the text is converted to the
    paired orthography before transliteration (снег → śnieh). Set it false to
    transliterate the input exactly as given (снег → snieh).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(max_length=MAX_TEXT_LENGTH)
    script: Script = Script.LACINKA
    from_script: Script | None = None
    convert: bool = True
    direction: Orthography | None = None


class TransliterateResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    script: Script
    #: the orthography the text passed through, or None when convert was false
    direction: Orthography | None = None
    #: graphemes the scheme could not render faithfully (a bare ь, foreign letters)
    unresolved: list[str] = Field(default_factory=list)


class BatchConvertRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    texts: list[str] = Field(max_length=MAX_BATCH)
    direction: Orthography
    explain: bool = False

    @field_validator("texts")
    @classmethod
    def _each_text_bounded(cls, texts: list[str]) -> list[str]:
        for i, t in enumerate(texts):
            if len(t) > MAX_TEXT_LENGTH:
                raise ValueError(f"texts[{i}] exceeds {MAX_TEXT_LENGTH} characters")
        return texts


class TokenExplanation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    target: str
    method: Method
    rule_id: str | None
    confidence: float


class RuleTraceOut(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    before: str
    after: str


class ChangeContext(BaseModel):
    """Why a cross-word rule fired: what it looked at outside the word itself.

    Present only on changes made by a rule that reads a neighbouring word. A ``null``
    context is therefore a positive statement — this change is reproducible from the
    word alone — not an absence of information.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: ``prev_word_vowel`` | ``prev_word`` | ``next_word``
    trigger: str
    #: the non-space characters the rule reached across (§18 Заўвага makes a hyphen or
    #: a quotation mark transparent); ``null`` when the words were merely adjacent
    across: str | None = None
    #: the § the trigger rests on, when the codification numbers it separately
    rule: str | None = None


class Change(BaseModel):
    """One word the converter changed, in the frozen cross-language shape.

    ``from`` is a Python keyword, so it is declared with an alias: the contract is the
    same in every language, so the language bends, not the contract.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    #: where ``to`` starts in the **output** text, in Unicode code points
    start: int
    #: one past the last code point of ``to`` in the output text
    end: int
    source: str = Field(serialization_alias="from", validation_alias="from")
    target: str = Field(serialization_alias="to", validation_alias="to")
    #: the cascade stage that resolved the word
    stage: Method
    #: the rule that fired; ``null`` for a plain lexicon hit, whose evidence is the entry
    rule: str | None = None
    citation: str | None = None
    context: ChangeContext | None = None

    @field_serializer("context")
    def _context_without_nulls(self, context: ChangeContext | None) -> dict[str, str] | None:
        """Omit the optional context keys rather than emitting them as null.

        `across` and `rule` are absent when they do not apply, which is how
        `docs/API.md` shows them and how `ConversionResult.to_dict()` writes them. A
        model that emitted `"across": null` here would make the FastAPI service and the
        serverless function disagree byte for byte on the same input — the exact class
        of parity bug this contract was frozen to prevent, and one that no test of
        either implementation alone would catch.
        """
        if context is None:
            return None
        out = {"trigger": context.trigger}
        if context.across is not None:
            out["across"] = context.across
        if context.rule is not None:
            out["rule"] = context.rule
        return out


class ConvertResponse(BaseModel):
    """The frozen conversion contract. See ``docs/API.md``.

    Every conversion endpoint returns exactly these six fields, and a port returns them
    too. ``explanations`` is the one documented exception: it appears only when the
    caller asks for it and is explicitly **outside** the frozen contract.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    #: the direction of travel, not the target orthography: ``n2t`` | ``t2n``
    direction: str
    #: the converter; moves in lockstep across implementations
    engine_version: str
    #: the data package; its own semver, independent of the engine
    data_version: str
    #: always present — the cascade has to decide what happened to every word in order
    #: to convert it, so reporting those decisions is not extra work and is not opt-in
    changes: list[Change] = Field(default_factory=list)
    #: words that matched an ambiguity trigger and that no stage resolved
    unresolved: list[str] = Field(default_factory=list)
    #: NOT part of the frozen contract: the per-rule trace, only when ``explain`` is set
    explanations: list[TokenExplanation] | None = None


class BatchConvertResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    results: list[ConvertResponse]


class LexiconResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    word: str
    direction: Orthography
    lexicon: str | None
    identity: bool
    rules: list[RuleTraceOut]
    result: TokenExplanation


class StatsResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    lexicon_size: int
    rule_count: int
    model_version: str | None


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = "ok"
