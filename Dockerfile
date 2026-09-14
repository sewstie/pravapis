# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY data ./data
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev \
 && uv run belnorm build-lexicon data/lexicon --out data/lexicon.marisa

FROM python:3.12-slim
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    BELNORM_DATA_DIR=/app/data \
    PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1
COPY --from=build /app/.venv ./.venv
COPY --from=build /app/src ./src
COPY --from=build /app/data ./data
RUN useradd --create-home belnorm && chown -R belnorm /app
USER belnorm
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "belnorm.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
