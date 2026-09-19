"""Framework-free HTTP layer for serverless deployment (Vercel Python).

Stdlib only on top of the converter: request validation, CORS, and the JSON
shapes the demo page and API clients use. ``api/convert.py`` at the repo root
is a thin ``BaseHTTPRequestHandler`` over :func:`handle`.

POST /api/convert, ``Content-Type: application/json``::

    {"text": "Не быў без мяне", "direction": "taraskievica", "explain": true}

- ``direction``: ``"taraskievica"`` (default) or ``"narkamauka"``
- ``script``: ``"cyrillic"`` only for now
- ``explain``: add per-token ``segments`` covering the whole output
- ``aggressive``: also apply optional transformations (default false)

200::

    {"result": "Ня быў без мяне", "direction": "taraskievica",
     "stats": {"words": 4, "changed": 1, "by_method": {"rule": 1, ...}},
     "segments": [{"text": "Ня", "source": "Не", "method": "rule",
                   "rule_id": "morph.particle", "changed": true,
                   "traces": [{"rule_id": "morph.particle", "before": "не", "after": "ня"}]},
                  {"text": " "}, ...]}
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final

import regex

from pravapis.normalize import sanitize
from pravapis.pipeline import Converter
from pravapis.tokenize import tokenize
from pravapis.translit import PAIRED, REVERSIBLE
from pravapis.types import Method, Orthography, Script, TokenKind

MAX_CHARS: Final[int] = 50_000
MAX_BODY_BYTES: Final[int] = MAX_CHARS * 4 + 4_096  # UTF-8 worst case plus JSON overhead
#: An oversized body is read and discarded up to this many bytes before the 413
#: goes out: answering while the client is still uploading resets the connection,
#: and the client sees a network error instead of the 413.
DRAIN_LIMIT_BYTES: Final[int] = 16 * 1024 * 1024
_DRAIN_CHUNK: Final[int] = 64 * 1024

DIRECTIONS: Final[dict[str, Orthography]] = {
    "taraskievica": Orthography.TARASKIEVICA,
    "narkamauka": Orthography.NARKAMAUKA,
}

#: Origins allowed to call the API cross-site. The demo page is same-origin.
ALLOWED_ORIGINS: Final[frozenset[str]] = frozenset({"https://paznaj.by", "https://www.paznaj.by"})
_LOCAL_ORIGIN: Final[regex.Pattern[str]] = regex.compile(
    r"^http://(localhost|127\.0\.0\.1)(:\d{1,5})?$"
)


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    body: dict[str, Any] | None
    headers: dict[str, str] = field(default_factory=dict)

    def encode(self) -> bytes:
        if self.body is None:
            return b""
        return json.dumps(self.body, ensure_ascii=False).encode("utf-8")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def cors_headers(origin: str | None) -> dict[str, str]:
    """CORS headers for an allowed ``Origin``; empty for any other (the browser then blocks)."""
    base = {"Vary": "Origin"}
    if origin and (origin in ALLOWED_ORIGINS or _LOCAL_ORIGIN.match(origin)):
        base["Access-Control-Allow-Origin"] = origin
    return base


def _segments(converter: Converter, text: str, direction: Orthography) -> list[dict[str, Any]]:
    """The output as a sequence of pieces: word segments carry how they were resolved."""
    tokens = tokenize(text)
    explanations = iter(converter.explain(text, direction))
    out: list[dict[str, Any]] = []
    for tok in tokens:
        if tok.kind is not TokenKind.WORD:
            out.append({"text": tok.text})
            continue
        e = next(explanations)
        out.append(
            {
                "text": e.target,
                "source": e.source,
                "method": e.method.value,
                "rule_id": e.rule_id,
                "changed": e.target != e.source,
                "traces": [
                    {"rule_id": t.rule_id, "before": t.before, "after": t.after} for t in e.traces
                ],
            }
        )
    return out


def convert_payload(converter: Converter, payload: Any) -> dict[str, Any]:
    """Validate a decoded JSON body and convert it. Raises :class:`ApiError`."""
    if not isinstance(payload, dict):
        raise ApiError(400, "body must be a JSON object")
    text = payload.get("text", "")
    if not isinstance(text, str):
        raise ApiError(400, "text must be a string")
    if len(text) > MAX_CHARS:
        raise ApiError(413, f"text longer than {MAX_CHARS} characters")
    name = payload.get("direction", "taraskievica")
    direction = DIRECTIONS.get(name) if isinstance(name, str) else None
    if direction is None:
        raise ApiError(400, "direction must be 'taraskievica' or 'narkamauka'")
    script_name = payload.get("script", "cyrillic")
    if not isinstance(script_name, str):
        raise ApiError(400, "script must be a string")
    try:
        script = Script(script_name)
    except ValueError:
        choices = ", ".join(f"'{s.value}'" for s in Script)
        raise ApiError(400, f"script must be one of {choices}") from None
    from_name = payload.get("from_script")
    if from_name is not None and not isinstance(from_name, str):
        raise ApiError(400, "from_script must be a string")
    from_script: Script | None = None
    if from_name is not None:
        try:
            from_script = Script(from_name)
        except ValueError:
            raise ApiError(400, f"unknown from_script {from_name!r}") from None
        if from_script not in REVERSIBLE:
            raise ApiError(
                422,
                f"{from_script.value} cannot be read back into Cyrillic: it does not "
                "write assimilative softness, so the reverse would not round-trip",
            )
    explain = payload.get("explain", False)
    if not isinstance(explain, bool):
        raise ApiError(400, "explain must be a boolean")
    aggressive = payload.get("aggressive", False)
    if not isinstance(aggressive, bool):
        raise ApiError(400, "aggressive must be a boolean")

    # aggressive: also rewrite forms the codification already allows (Фёдар → Хведар,
    # і → й after a vowel). Off by default: converting an allowed form is a false positive.
    converter = converter.variant(aggressive)

    # Reading a Latin script back: transliterate first, then convert. The orthography
    # the caller asked for is the one they get.
    if from_script is not None:
        return {
            "result": converter.read_script(text, from_script, direction),
            "direction": direction.value,
            "from_script": from_script.value,
            "script": Script.CYRILLIC.value,
            "aggressive": aggressive,
        }

    text = sanitize(text)

    # Writing a Latin script: convert to the orthography that scheme is paired with,
    # then transliterate. See data/TRANSLIT.md, "Script is a separate axis".
    if script.is_latin:
        convert_first = payload.get("convert", True)
        if not isinstance(convert_first, bool):
            raise ApiError(400, "convert must be a boolean")
        return {
            "result": converter.render(text, script, convert=convert_first),
            "direction": PAIRED[script].value if convert_first else None,
            "script": script.value,
            "aggressive": aggressive,
        }

    result = converter.convert(text, direction)
    by_method = {m.value: 0 for m in Method}
    for c in result.conversions:
        if c.target != c.source:
            by_method[c.method.value] += 1
    body: dict[str, Any] = {
        "result": result.text,
        "direction": direction.value,
        "script": Script.CYRILLIC.value,
        "aggressive": aggressive,
        "stats": {
            "words": len(result.conversions),
            "changed": sum(by_method.values()),
            "by_method": by_method,
        },
    }
    if explain:
        body["segments"] = _segments(converter, text, direction)
    return body


def handle(
    converter: Converter,
    method: str,
    headers: dict[str, str],
    read_body: Callable[[int], bytes],
) -> Response:
    """Route one request.

    ``headers`` must have lowercase keys; ``read_body(n)`` returns the raw body bytes.
    """
    cors = cors_headers(headers.get("origin"))
    common = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", **cors}
    if method == "OPTIONS":
        pre = dict(common)
        if "Access-Control-Allow-Origin" in cors:
            pre.update(
                {
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Max-Age": "86400",
                }
            )
        return Response(204, None, pre)
    if method != "POST":
        return Response(405, {"error": "use POST"}, {**common, "Allow": "POST, OPTIONS"})
    try:
        if "application/json" not in headers.get("content-type", ""):
            raise ApiError(415, "Content-Type must be application/json")
        try:
            length = int(headers.get("content-length") or 0)
        except ValueError:
            raise ApiError(400, "invalid Content-Length") from None
        if length > MAX_BODY_BYTES:
            remaining = min(length, DRAIN_LIMIT_BYTES)
            while remaining > 0:
                chunk = read_body(min(_DRAIN_CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
            raise ApiError(
                413, f"request body too large (text is limited to {MAX_CHARS} characters)"
            )
        raw = read_body(length)
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "body is not valid UTF-8 JSON") from None
        return Response(200, convert_payload(converter, payload), common)
    except ApiError as exc:
        return Response(exc.status, {"error": exc.message}, common)
