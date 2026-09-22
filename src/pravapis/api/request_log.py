"""Metadata-only request logging.

A log line here carries exactly seven fields: endpoint, direction, char count,
duration, engine version, data version, status. It never carries request text, a
hash of request text, or a flagged "unresolved" token — a flagged token is still a
fragment of user input, however short. See docs/API.md, "Privacy".

``scripts/check_no_request_text_logging.py`` is the CI guard that keeps it that way:
it fails the build if a log call in ``src/pravapis/api/`` sits within a few lines of
an identifier that could hold request text or the unresolved list, so a future edit
cannot reintroduce either by accident.

``direction`` and ``char_count`` are read from ``request.state``, set by a route
handler that opts in (``request.state.direction = req.direction``,
``request.state.char_count = len(req.text)`` — a length, never the string). A
handler that does not set them logs as ``direction=- chars=-``; this module never
reads the request or response body itself, so it cannot log what it never touches.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from functools import lru_cache

from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger("pravapis.api.request")


@lru_cache(maxsize=1)
def _versions() -> tuple[str, str]:
    """(engine_version, data_version) — read once; neither changes while a process runs."""
    from pravapis import __version__
    from pravapis.dataversion import read_data_version

    try:
        data_version = read_data_version()
    except Exception:  # pragma: no cover - a missing data/VERSION is a startup bug
        data_version = "unknown"
    return __version__, data_version


async def log_request_metadata(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    engine_version, data_version = _versions()
    log.info(
        "endpoint=%s direction=%s chars=%s duration_ms=%.2f engine_version=%s "
        "data_version=%s status=%d",
        request.url.path,
        getattr(request.state, "direction", "-"),
        getattr(request.state, "char_count", "-"),
        duration_ms,
        engine_version,
        data_version,
        response.status_code,
    )
    return response
