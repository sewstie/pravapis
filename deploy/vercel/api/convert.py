"""Vercel Python serverless function: POST /api/convert.

Lives in the Paznaj Next.js repo as ``api/convert.py``; the converter code and
its data are vendored next to it in ``api/_belnorm/`` (the leading underscore
keeps Vercel from turning that folder into functions). Produced by
``scripts/export_vercel.py`` in the belnorm repo — do not edit the vendored
copy by hand.

Request (JSON):
    {"text": "Снег і свет", "direction": "taraskievica"}
    direction: "taraskievica" (default) or "narkamauka"
    script:    "cyrillic" (default); "latin" is not supported and returns 422

Response 200 (JSON):
    {"result": "Сьнег і сьвет", "direction": "taraskievica",
     "stats": {"identity": 0, "lexicon": 0, "rule": 2, "model": 0, "unknown": 1}}

Errors are JSON {"error": "..."} with 400, 405, 413, 415 or 422.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

VENDOR = Path(__file__).resolve().parent / "_belnorm"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from belnorm.config import Config  # noqa: E402
from belnorm.pipeline import Converter  # noqa: E402
from belnorm.types import Orthography  # noqa: E402

MAX_CHARS = 50_000
MAX_BODY_BYTES = MAX_CHARS * 4 + 4_096  # UTF-8 worst case plus JSON overhead

DIRECTIONS = {
    "taraskievica": Orthography.TARASKIEVICA,
    "narkamauka": Orthography.NARKAMAUKA,
}

# Loaded once per cold start and reused by every invocation on this instance.
CONVERTER = Converter.from_config(Config.default(VENDOR / "data"))


class ConvertError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def convert_payload(payload: Any) -> dict[str, Any]:
    """Validate a decoded JSON body and convert it. Raises ConvertError."""
    if not isinstance(payload, dict):
        raise ConvertError(400, "body must be a JSON object")
    text = payload.get("text", "")
    if not isinstance(text, str):
        raise ConvertError(400, "text must be a string")
    if len(text) > MAX_CHARS:
        raise ConvertError(413, f"text longer than {MAX_CHARS} characters")
    direction_name = payload.get("direction", "taraskievica")
    direction = DIRECTIONS.get(direction_name) if isinstance(direction_name, str) else None
    if direction is None:
        raise ConvertError(400, "direction must be 'taraskievica' or 'narkamauka'")
    script = payload.get("script", "cyrillic")
    if script != "cyrillic":
        raise ConvertError(422, "only script='cyrillic' is supported")
    if not text.strip():
        return {"result": text, "direction": direction.value, "stats": {}}
    converted = CONVERTER.convert(text, direction)
    return {
        "result": converted.text,
        "direction": direction.value,
        "stats": {m.value: n for m, n in converted.stats.items()},
    }


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: dict[str, Any], extra: dict[str, str] | None = None) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        try:
            ctype = self.headers.get("Content-Type", "")
            if "application/json" not in ctype:
                raise ConvertError(415, "Content-Type must be application/json")
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                raise ConvertError(413, "request body too large")
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ConvertError(400, "body is not valid UTF-8 JSON") from None
            self._send(200, convert_payload(payload))
        except ConvertError as exc:
            self._send(exc.status, {"error": exc.message})
        except ValueError:
            self._send(400, {"error": "invalid Content-Length"})

    def _method_not_allowed(self) -> None:
        self._send(405, {"error": "use POST"}, {"Allow": "POST"})

    do_GET = do_PUT = do_DELETE = do_PATCH = _method_not_allowed

    def log_message(self, format: str, *args: Any) -> None:
        return  # Vercel captures stdout; do not log request bodies
