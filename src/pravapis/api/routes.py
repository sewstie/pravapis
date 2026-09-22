"""HTTP endpoints. The converter is built once in the app lifespan (see ``main.py``)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from pravapis import __version__
from pravapis.api.cache import ResponseCache, cache_key, etag_for
from pravapis.api.schemas import (
    BatchConvertRequest,
    BatchConvertResponse,
    Change,
    ChangeContext,
    ConvertRequest,
    ConvertResponse,
    HealthResponse,
    LexiconResponse,
    RuleTraceOut,
    StatsResponse,
    TokenExplanation,
    TransliterateRequest,
    TransliterateResponse,
    VersionResponse,
)
from pravapis.dataversion import compute_data_hash, read_data_version
from pravapis.normalize import sanitize
from pravapis.pipeline import Converter
from pravapis.translit import PAIRED, REVERSIBLE
from pravapis.types import ConversionResult, Orthography, Script

router = APIRouter()

#: /v1/convert has no script of its own (that is /v1/transliterate); fixed so the
#: cache key's shape is ready for that endpoint to share this cache later.
CONVERT_SCRIPT = "cyrillic"

UnresolvedQuery = Annotated[
    bool,
    Query(
        description="Also report words the converter declined to decide on. Off by "
        'default — see docs/API.md, "Off by default: measured, not guessed".'
    ),
]


def get_converter(request: Request) -> Converter:
    converter: Converter = request.app.state.converter
    return converter


def get_cache(request: Request) -> ResponseCache:
    cache: ResponseCache = request.app.state.cache
    return cache


ConverterDep = Annotated[Converter, Depends(get_converter)]
CacheDep = Annotated[ResponseCache, Depends(get_cache)]


@lru_cache(maxsize=1)
def _data_version() -> str:
    """Cached: the data version does not change while a process runs."""
    return read_data_version()


def _convert_cached(
    converter: Converter, cache: ResponseCache, text: str, direction: Orthography, unresolved: bool
) -> tuple[ConversionResult, tuple[str, str, str, bool, str]]:
    key = cache_key(text, direction, CONVERT_SCRIPT, unresolved, _data_version())
    result = cache.get_or_set(
        key, lambda: converter.convert(text, direction, unresolved=unresolved)
    )
    return result, key


def _to_response(result: ConversionResult, explain: bool) -> ConvertResponse:
    """Build the frozen response. The shape lives in `pravapis.types.ConversionResult`.

    Built from `result.to_dict()` rather than field by field, so the FastAPI service and
    the library's own public shape cannot drift: there is one place that decides what a
    conversion looks like on the wire.
    """
    payload = result.to_dict()
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
    return ConvertResponse(
        text=payload["text"],
        direction=payload["direction"],
        engine_version=payload["engine_version"],
        data_version=payload["data_version"],
        changes=[
            Change(
                start=change["start"],
                end=change["end"],
                **{"from": change["from"], "to": change["to"]},
                stage=change["stage"],
                rule=change["rule"],
                citation=change["citation"],
                context=(None if change["context"] is None else ChangeContext(**change["context"])),
            )
            for change in payload["changes"]
        ],
        unresolved=payload["unresolved"],
        explanations=explanations,
    )


@router.post("/v1/convert", response_model=ConvertResponse)
def convert(
    req: ConvertRequest,
    converter: ConverterDep,
    cache: CacheDep,
    response: Response,
    unresolved: UnresolvedQuery = False,
) -> ConvertResponse:
    result, key = _convert_cached(converter, cache, req.text, req.direction, unresolved)
    response.headers["ETag"] = etag_for(key)
    return _to_response(result, req.explain)


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
        # Latin → Latin goes through Cyrillic and through both orthographies, because the
        # two Latin schemes are paired with different ones. See data/TRANSLIT.md.
        if req.script.is_latin and req.script is not req.from_script:
            return TransliterateResponse(
                text=converter.transcode(req.text, req.script, from_script=req.from_script),
                script=req.script,
                direction=PAIRED[req.script],
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
def convert_batch(
    req: BatchConvertRequest,
    converter: ConverterDep,
    cache: CacheDep,
    unresolved: UnresolvedQuery = False,
) -> BatchConvertResponse:
    results = []
    for t in req.texts:
        result, _key = _convert_cached(converter, cache, t, req.direction, unresolved)
        results.append(_to_response(result, req.explain))
    return BatchConvertResponse(results=results)


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


@router.get("/v1/version", response_model=VersionResponse)
def version() -> VersionResponse:
    """Which engine and which data this instance is running — the same data_hash a
    precompiled artifact's filename carries (pravapis.artifact), by construction:
    both call pravapis.dataversion.compute_data_hash()."""
    return VersionResponse(
        engine_version=__version__,
        data_version=_data_version(),
        data_hash=compute_data_hash(),
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()
