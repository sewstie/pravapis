"""Request/response models for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pravapis.types import Method, Orthography

MAX_TEXT_LENGTH = 50_000
MAX_BATCH = 100


class ConvertRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(max_length=MAX_TEXT_LENGTH)
    direction: Orthography
    explain: bool = False


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


class ConvertResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    stats: dict[Method, int]
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
