"""Vendored variant of the /api/convert function (for embedding in another repo).

The optional standalone adapter lives in deploy/vercel/standalone/convert.py. This copy
is produced by scripts/export_vercel.py for a host project: it imports the
converter from api/_pravapis/ (leading underscore: not a function). Request
handling, validation and CORS live in pravapis.webapi, shared by both.
"""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

VENDOR = Path(__file__).resolve().parent / "_pravapis"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from pravapis.config import Config  # noqa: E402
from pravapis.pipeline import Converter  # noqa: E402
from pravapis.webapi import handle  # noqa: E402

# Built once per cold start, reused by every request on this instance.
CONVERTER = Converter.from_config(Config.default(VENDOR / "data"))


class handler(BaseHTTPRequestHandler):
    def _dispatch(self) -> None:
        headers = {k.lower(): v for k, v in self.headers.items()}
        resp = handle(CONVERTER, self.command, headers, self.rfile.read)
        data = resp.encode()
        self.send_response(resp.status)
        if resp.body is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for k, v in resp.headers.items():
            self.send_header(k, v)
        self.end_headers()
        if data:
            self.wfile.write(data)

    do_POST = do_OPTIONS = do_GET = do_PUT = do_DELETE = do_PATCH = _dispatch

    def log_message(self, format: str, *args: Any) -> None:
        return  # do not log request bodies
