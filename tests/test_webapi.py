"""The standalone Vercel function: api/convert.py over belnorm.webapi."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from belnorm.pipeline import Converter
from belnorm.webapi import ApiError, convert_payload, cors_headers, handle

ROOT = Path(__file__).resolve().parent.parent


def _post(converter: Converter, body: object, **headers: str) -> tuple[int, dict, dict]:
    raw = json.dumps(body, ensure_ascii=False).encode()
    hdrs = {"content-type": "application/json", "content-length": str(len(raw)), **headers}
    resp = handle(converter, "POST", hdrs, io.BytesIO(raw).read)
    return resp.status, resp.body or {}, resp.headers


def test_explain_segments_rebuild_the_output(converter: Converter) -> None:
    body = convert_payload(
        converter, {"text": "Не быў у Мінску, план сістэмы — снег.", "explain": True}
    )
    assert body["result"] == "Ня быў у Менску, плян сыстэмы — сьнег."
    assert "".join(s["text"] for s in body["segments"]) == body["result"]
    changed = {s["source"]: s for s in body["segments"] if s.get("changed")}
    assert changed["Не"]["method"] == "rule"
    assert changed["Не"]["traces"][0]["rule_id"] == "morph.particle"
    assert changed["Мінску"]["method"] == "lexicon"
    assert changed["снег"]["traces"] == [
        {"rule_id": "palat.assim", "before": "снег", "after": "сьнег"}
    ]
    st = body["stats"]
    assert st["words"] == 7
    assert st["changed"] == 5
    assert st["by_method"]["lexicon"] + st["by_method"]["rule"] == 5


def test_no_segments_without_explain(converter: Converter) -> None:
    assert "segments" not in convert_payload(converter, {"text": "снег"})


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ([], 400),
        ({"text": 1}, 400),
        ({"text": "а", "direction": "latin"}, 400),
        ({"text": "а", "script": "latin"}, 422),
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
    assert status == 200 and body["result"] == "сьнег"
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
}
import belnorm
out["belnorm_file"] = belnorm.__file__
out["heavy"] = sorted(m for m in sys.modules if m.split(".")[0] in
    {"fastapi", "starlette", "uvicorn", "typer", "rich", "sklearn", "joblib", "pandas"}
    or m.startswith(("belnorm.disambiguate", "belnorm.api", "belnorm.cli", "belnorm.metrics")))
srv.shutdown()
print(json.dumps(out, ensure_ascii=False))
"""


def test_root_function_over_http() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", DRIVER, str(ROOT / "api" / "convert.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=120,
    )
    r = json.loads(proc.stdout)
    status, body, headers = r["post"]
    assert status == 200
    assert body["result"] == "Ня быў у Менску"
    assert headers["Access-Control-Allow-Origin"] == "https://paznaj.by"
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert r["preflight"][0] == 204
    assert r["preflight"][2]["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert Path(r["belnorm_file"]).is_relative_to(ROOT / "src")
    assert r["heavy"] == []


def test_vercel_json_excludes_dev_folders() -> None:
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert cfg["outputDirectory"] == "public"
    exclude = cfg["functions"]["api/convert.py"]["excludeFiles"]
    for folder in ("tests", "benchmarks", "scripts", "data/eval"):
        assert folder in exclude


def test_requirements_match_runtime_imports() -> None:
    reqs = {
        line.split("==")[0].lower()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    assert reqs == {"regex", "marisa-trie", "pyyaml", "pydantic"}
