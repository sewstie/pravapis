from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_openapi_json_is_not_stale() -> None:
    """Regenerating from the current routes/schemas must reproduce the committed
    bytes exactly — the same check `scripts/export_openapi.py --check` runs in CI.
    If this fails, a route or a Pydantic model changed and nobody regenerated
    openapi.json; docs/API.md, "Changing this contract" says what kind of version
    bump that change needs.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from export_openapi import generate, render
    finally:
        sys.path.pop(0)

    committed = ROOT / "openapi.json"
    assert committed.is_file(), "run `python scripts/export_openapi.py` to create it"
    assert committed.read_text(encoding="utf-8") == render(generate()), (
        "openapi.json is stale — run `python scripts/export_openapi.py` and commit it"
    )


def test_openapi_schema_lists_the_documented_endpoints() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from export_openapi import generate
    finally:
        sys.path.pop(0)

    paths = set(generate()["paths"])
    for expected in (
        "/v1/convert",
        "/v1/convert/batch",
        "/v1/transliterate",
        "/v1/lexicon/{word}",
        "/v1/stats",
        "/v1/version",
        "/health",
    ):
        assert expected in paths
