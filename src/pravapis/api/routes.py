"""HTTP endpoints. The converter is built once in the app lifespan (see ``main.py``)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from pravapis import __version__
from pravapis.api.schemas import (
    BatchConvertRequest,
    BatchConvertResponse,
    ConvertRequest,
    ConvertResponse,
    HealthResponse,
    LexiconResponse,
    RuleTraceOut,
    StatsResponse,
    TokenExplanation,
    TransliterateRequest,
    TransliterateResponse,
)
from pravapis.normalize import sanitize
from pravapis.pipeline import Converter
from pravapis.translit import PAIRED, REVERSIBLE
from pravapis.types import ConversionResult, Orthography, Script

router = APIRouter()


def get_converter(request: Request) -> Converter:
    converter: Converter = request.app.state.converter
    return converter


ConverterDep = Annotated[Converter, Depends(get_converter)]


def _to_response(
    converter: Converter, text: str, direction: Orthography, explain: bool
) -> ConvertResponse:
    result: ConversionResult = converter.convert(text, direction)
    explanations = None
    if explain:
        explanations = [
            TokenExplanation(
                source=c.source,
                target=c.target,
                method=c.method,
                rule_id=c.rule_id,
                confidence=c.confidence,
            )
            for c in result.conversions
        ]
    return ConvertResponse(text=result.text, stats=result.stats, explanations=explanations)


@router.post("/v1/convert", response_model=ConvertResponse)
def convert(req: ConvertRequest, converter: ConverterDep) -> ConvertResponse:
    return _to_response(converter, req.text, req.direction, req.explain)


@router.post("/v1/transliterate", response_model=TransliterateResponse)
def transliterate(req: TransliterateRequest, converter: ConverterDep) -> TransliterateResponse:
    """Cyrillic ↔ Latin. See data/TRANSLIT.md for the schemes and their sources."""
    if req.from_script is not None:
        if req.from_script not in REVERSIBLE:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{req.from_script.value} cannot be read back into Cyrillic: it does "
                    "not write assimilative softness, so the reverse would not round-trip"
                ),
            )
        text = converter.read_script(req.text, req.from_script, req.direction)
        return TransliterateResponse(text=text, script=Script.CYRILLIC, direction=req.direction)
    if req.script is Script.CYRILLIC:
        raise HTTPException(
            status_code=422,
            detail="script='cyrillic' needs a from_script to read back from",
        )
    result = converter.render_result(req.text, req.script, convert=req.convert)
    return TransliterateResponse(
        text=result.text,
        script=req.script,
        direction=PAIRED[req.script] if req.convert else None,
        unresolved=list(result.unresolved),
    )


@router.post("/v1/convert/batch", response_model=BatchConvertResponse)
def convert_batch(req: BatchConvertRequest, converter: ConverterDep) -> BatchConvertResponse:
    return BatchConvertResponse(
        results=[_to_response(converter, t, req.direction, req.explain) for t in req.texts]
    )


@router.get("/v1/lexicon/{word}", response_model=LexiconResponse)
def lexicon_lookup(
    word: str,
    converter: ConverterDep,
    direction: Orthography = Orthography.TARASKIEVICA,
) -> LexiconResponse:
    word = sanitize(word)
    conv = converter.convert_word(word, direction)
    traces = converter.engine.explain(word.lower(), direction)
    return LexiconResponse(
        word=word,
        direction=direction,
        lexicon=converter.lexicon.lookup_ci(word, direction),
        identity=converter.lexicon.is_identity(word),
        rules=[RuleTraceOut(rule_id=t.rule_id, before=t.before, after=t.after) for t in traces],
        result=TokenExplanation(
            source=conv.source,
            target=conv.target,
            method=conv.method,
            rule_id=conv.rule_id,
            confidence=conv.confidence,
        ),
    )


@router.get("/v1/stats", response_model=StatsResponse)
def stats(converter: ConverterDep) -> StatsResponse:
    return StatsResponse(
        version=__version__,
        lexicon_size=len(converter.lexicon),
        rule_count=len(converter.engine),
        model_version=converter.model_version,
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()
