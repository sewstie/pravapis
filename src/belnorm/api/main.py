"""FastAPI application factory.

The lexicon, rules and (optional) model are loaded exactly once, inside the
lifespan handler, and attached to ``app.state``. Run with::

    uvicorn belnorm.api.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from belnorm import __version__
from belnorm.api.routes import router
from belnorm.config import Config
from belnorm.pipeline import Converter

log = logging.getLogger(__name__)

ENV_CONFIG = "BELNORM_CONFIG"


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
        log.info(
            "belnorm %s ready: %s, %d rules, model=%s",
            __version__,
            converter.lexicon,
            len(converter.engine),
            converter.model_version,
        )
        yield

    app = FastAPI(
        title="belnorm",
        description="Bidirectional Belarusian orthography converter (Narkamaŭka ↔ Taraškievica)",
        version=__version__,
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
