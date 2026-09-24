"""Optional Python HTTP adapter (not deployed by the static website).

For separate Python deployments: the package is imported from src/, and the
converter is loaded whole from data/pravapis-<hash>.bin — one pickle.load, no YAML or
TSV parsing at cold start or on any request. That file is built by
`pravapis build-artifact` from exactly the sources data/MANIFEST lists (see
pravapis.artifact); it is not generated here. All request handling lives in
pravapis.webapi; this file only adapts it to BaseHTTPRequestHandler.
"""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pravapis.artifact import ArtifactError, load_artifact  # noqa: E402
from pravapis.webapi import handle  # noqa: E402

DATA = ROOT / "data"
_candidates = sorted(DATA.glob("pravapis-*.bin"))
if not _candidates:
    raise ArtifactError(
        f"{DATA}: no pravapis-<hash>.bin artifact; run `pravapis build-artifact` first"
    )
if len(_candidates) > 1:
    raise ArtifactError(f"{DATA}: more than one artifact ({[p.name for p in _candidates]})")

# Built once per cold start, reused by every request on this instance.
CONVERTER = load_artifact(_candidates[0]).converter()


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
