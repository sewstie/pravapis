"""The optional standalone Python adapter over pravapis.webapi."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pravapis.artifact import artifact_filename, build_artifact
from pravapis.dataversion import compute_data_hash
from pravapis.pipeline import Converter
from pravapis.webapi import ApiError, convert_payload, cors_headers, handle

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STANDALONE = ROOT / "deploy" / "vercel" / "standalone"


@pytest.fixture(scope="module")
def built_artifact() -> Path:
    """The standalone adapter loads data/pravapis-<hash>.bin at import — build it once for
    the subprocess test below rather than requiring a committed (gitignored) artifact."""
    existing = DATA / artifact_filename(compute_data_hash(DATA))
    if existing.is_file():
        return existing
    return build_artifact(DATA, DATA)


def _post(converter: Converter, body: object, **headers: str) -> tuple[int, dict, dict]:
    raw = json.dumps(body, ensure_ascii=False).encode()
    hdrs = {"content-type": "application/json", "content-length": str(len(raw)), **headers}
    resp = handle(converter, "POST", hdrs, io.BytesIO(raw).read)
    return resp.status, resp.body or {}, resp.headers


def test_explain_segments_rebuild_the_output(converter: Converter) -> None:
    body = convert_payload(
        converter, {"text": "Не быў у Мінску, план сістэмы — снег.", "explain": True}
    )
    assert body["text"] == "Ня быў у Менску, плян сыстэмы — сьнег."
    assert "".join(s["text"] for s in body["segments"]) == body["text"]
    changed = {s["source"]: s for s in body["segments"] if s.get("changed")}
    assert changed["Не"]["method"] == "rule"
    assert changed["Не"]["traces"][0]["rule_id"] == "morph.particle"
    assert changed["Мінску"]["method"] == "lexicon"
    assert changed["снег"]["traces"] == [
        {"rule_id": "palat.assim", "before": "снег", "after": "сьнег"}
    ]
    # `stats` left the response when the contract was frozen (docs/API.md): the same
    # counts are derivable from `changes`, and an extra top-level key is exactly the
    # kind of thing a port would omit without anyone noticing.
    assert len(body["changes"]) == 5
    stages = [c["stage"] for c in body["changes"]]
    assert stages.count("lexicon") + stages.count("rule") == 5
    assert len([s for s in body["segments"] if "source" in s]) == 7


def test_aggressive_field(converter: Converter) -> None:
    """`aggressive` is a request option, and the response no longer echoes it.

    The frozen contract has six fields and an echo is not one of them; what the option
    did is visible in the output itself, which is the thing worth asserting anyway.
    """
    default = convert_payload(converter, {"text": "Фёдар і Мама"})
    assert default["text"] == "Фёдар і Мама"
    assert "aggressive" not in default
    aggressive = convert_payload(converter, {"text": "Фёдар і Мама", "aggressive": True})
    assert aggressive["text"] == "Хведар і Мама"  # і after a consonant stays
    assert convert_payload(converter, {"text": "Мама і тата", "aggressive": True})["text"] == (
        "Мама й тата"
    )
    with pytest.raises(ApiError) as exc:
        convert_payload(converter, {"text": "а", "aggressive": "yes"})
    assert exc.value.status == 400


def test_no_segments_without_explain(converter: Converter) -> None:
    assert "segments" not in convert_payload(converter, {"text": "снег"})


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ([], 400),
        ({"text": 1}, 400),
        ({"text": "а", "direction": "latin"}, 400),
        ({"text": "а", "script": "latin"}, 400),  # not a known script
        ({"text": "а", "from_script": "official"}, 422),  # known, but not reversible
        ({"text": "а", "script": "lacinka", "convert": "yes"}, 400),
        ({"text": "а", "explain": "yes"}, 400),
        ({"text": "а" * 50_001}, 413),
    ],
)
def test_validation(converter: Converter, payload: object, status: int) -> None:
    with pytest.raises(ApiError) as exc:
        convert_payload(converter, payload)
    assert exc.value.status == status


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [
        ("https://paznaj.by", True),
        ("https://www.paznaj.by", True),
        ("http://localhost:3000", True),
        ("http://127.0.0.1:5173", True),
        ("http://localhost", True),
        ("http://paznaj.by", False),  # not https
        ("https://paznaj.by.evil.example", False),
        ("https://localhost:3000", False),
        ("http://localhost.evil.example", False),
        (None, False),
    ],
)
def test_cors_origins(origin: str | None, allowed: bool) -> None:
    h = cors_headers(origin)
    assert h["Vary"] == "Origin"
    assert ("Access-Control-Allow-Origin" in h) is allowed
    if allowed:
        assert h["Access-Control-Allow-Origin"] == origin


def test_preflight(converter: Converter) -> None:
    resp = handle(converter, "OPTIONS", {"origin": "https://paznaj.by"}, io.BytesIO().read)
    assert resp.status == 204 and resp.body is None
    assert resp.headers["Access-Control-Allow-Origin"] == "https://paznaj.by"
    assert resp.headers["Access-Control-Allow-Methods"] == "POST, OPTIONS"
    assert resp.headers["Access-Control-Allow-Headers"] == "Content-Type"
    denied = handle(converter, "OPTIONS", {"origin": "https://evil.example"}, io.BytesIO().read)
    assert denied.status == 204
    assert "Access-Control-Allow-Origin" not in denied.headers


def test_post_carries_cors_for_allowed_origin(converter: Converter) -> None:
    status, body, headers = _post(converter, {"text": "снег"}, origin="http://localhost:3000")
    assert status == 200 and body["text"] == "сьнег"
    assert headers["Access-Control-Allow-Origin"] == "http://localhost:3000"


def test_method_not_allowed(converter: Converter) -> None:
    resp = handle(converter, "GET", {}, io.BytesIO().read)
    assert resp.status == 405 and resp.headers["Allow"] == "POST, OPTIONS"


DRIVER = r"""
import importlib.util, json, sys, threading, urllib.request, urllib.error
from http.server import HTTPServer
spec = importlib.util.spec_from_file_location("convert", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
srv = HTTPServer(("127.0.0.1", 0), mod.handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/api/convert"
def call(method, body=None, **headers):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null"), dict(e.headers)
out = {
    "post": call("POST", {"text": "Не быў у Мінску", "explain": True},
                 **{"Content-Type": "application/json", "Origin": "https://paznaj.by"}),
    "preflight": call("OPTIONS", **{"Origin": "http://localhost:3000",
                                    "Access-Control-Request-Method": "POST"}),
    # larger than MAX_BODY_BYTES: must be a JSON 413, not a connection reset
    "huge": call("POST", {"text": "снег " * 80_000}, **{"Content-Type": "application/json"}),
}
import pravapis
out["pravapis_file"] = pravapis.__file__
out["heavy"] = sorted(m for m in sys.modules if m.split(".")[0] in
    {"fastapi", "starlette", "uvicorn", "typer", "rich", "sklearn", "joblib", "pandas"}
    or m.startswith(("pravapis.disambiguate", "pravapis.api", "pravapis.cli", "pravapis.metrics")))
srv.shutdown()
print(json.dumps(out, ensure_ascii=False))
"""


def test_root_function_over_http(built_artifact: Path) -> None:
    del built_artifact  # exists on disk; the adapter finds it by globbing data/
    proc = subprocess.run(
        [sys.executable, "-c", DRIVER, str(STANDALONE / "convert.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        # The driver prints Cyrillic; without this the child encodes stdout with the
        # console codepage (cp1252 on Windows) and dies before it can answer.
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=True,
        timeout=120,
    )
    r = json.loads(proc.stdout)
    status, body, headers = r["post"]
    assert status == 200
    assert body["text"] == "Ня быў у Менску"
    assert headers["Access-Control-Allow-Origin"] == "https://paznaj.by"
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert r["preflight"][0] == 204
    assert r["preflight"][2]["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert r["huge"][0] == 413
    assert "too large" in r["huge"][1]["error"]
    assert Path(r["pravapis_file"]).is_relative_to(ROOT / "src")
    assert r["heavy"] == []


def test_website_has_no_python_function() -> None:
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert "functions" not in cfg
    assert cfg["buildCommand"] == "npm run build --prefix website"
    assert not (ROOT / "api" / "convert.py").exists()


def test_requirements_match_runtime_imports() -> None:
    reqs = {
        line.split("==")[0].lower()
        for line in (STANDALONE / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    assert reqs == {"regex", "marisa-trie", "pyyaml", "pydantic"}
