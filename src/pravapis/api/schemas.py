"""Request/response models for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class Change(BaseModel):
    """One word the converter changed, in the frozen cross-language shape.

    The field names are the wire names — ``from`` and ``class`` are Python keywords, so
    they are declared with aliases and the contract, not the language, wins.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    source: str = Field(serialization_alias="from", validation_alias="from")
    target: str = Field(serialization_alias="to", validation_alias="to")
    #: index into the sanitized input; see pravapis.types.ConversionResult
    offset: int
    rule: str | None = None
    #: the cascade stage that resolved the word
    method: Method = Field(serialization_alias="class", validation_alias="class")
    citation: str | None = None


class ConvertResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    stats: dict[Method, int]
    #: always present — the cascade has to decide what happened to every word in order
    #: to convert it, so reporting those decisions is not extra work and is not opt-in
    changes: list[Change] = Field(default_factory=list)
    #: the per-rule trace, which is the only part an explanation adds over `changes`
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
