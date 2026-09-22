"""FastAPI application factory.

The lexicon, rules and (optional) model are loaded exactly once, inside the
lifespan handler, and attached to ``app.state``. Run with::

    uvicorn pravapis.api.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pravapis import __version__
from pravapis.api.cache import ResponseCache
from pravapis.api.request_log import log_request_metadata
from pravapis.api.routes import router
from pravapis.config import Config
from pravapis.pipeline import Converter

log = logging.getLogger(__name__)

ENV_CONFIG = "PRAVAPIS_CONFIG"


def _resolve_config(config: Config | Path | None) -> Config:
    if isinstance(config, Config):
        return config
    if config is not None:
        return Config.load(config)
    env = os.environ.get(ENV_CONFIG)
    return Config.load(Path(env)) if env else Config.default()


def create_app(config: Config | Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved = _resolve_config(config)
        converter = Converter.from_config(resolved)
        app.state.converter = converter
        app.state.config = resolved
        app.state.cache = ResponseCache()
        log.info(
            "pravapis %s ready: %s, %d rules, model=%s",
            __version__,
            converter.lexicon,
            len(converter.engine),
            converter.model_version,
        )
        yield

    app = FastAPI(
        title="pravapis",
        description="Bidirectional Belarusian orthography converter (Narkamaŭka ↔ Taraškievica)",
        version=__version__,
        lifespan=lifespan,
    )
    app.include_router(router)
    # Public, read-only, unauthenticated API: any origin may call it, and it sets no
    # cookies and reads none — allow_credentials must stay False, since CORS forbids
    # combining it with a wildcard origin (and there is nothing here credentials
    # would protect anyway).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(log_request_metadata)
    return app


app = create_app()
