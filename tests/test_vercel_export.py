"""The exported Vercel function works standalone and stays small."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Serves the exported api/convert.py handler on a free port, fires requests, prints results.
DRIVER = r"""
import importlib.util, json, sys, threading, urllib.request, urllib.error
from http.server import HTTPServer
api = sys.argv[1]
spec = importlib.util.spec_from_file_location("convert", api + "/convert.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
srv = HTTPServer(("127.0.0.1", 0), mod.handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/api/convert"

def call(method, body=None, ctype="application/json"):
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e), dict(e.headers)

out = {
    "n2t": call("POST", {"text": "Снег і свет у Еўропе, план сістэмы. Не быў без мяне."}),
    "t2n": call("POST", {"text": "Сьнег і сьвет", "direction": "narkamauka"}),
    "empty": call("POST", {"text": "   "}),
    "latin": call("POST", {"text": "снег", "script": "latin"}),
    "bad_dir": call("POST", {"text": "снег", "direction": "x"}),
    "not_str": call("POST", {"text": 5}),
    "too_long": call("POST", {"text": "а" * 50_001}),
    "bad_json": call("POST", b"{nope"),
    "bad_ctype": call("POST", b"text=snieh", "application/x-www-form-urlencoded"),
    "get": call("GET"),
}
import pravapis
out["pravapis_file"] = pravapis.__file__
out["loaded"] = sorted(m for m in sys.modules if m.split(".")[0] in
    {"fastapi", "starlette", "uvicorn", "typer", "rich", "sklearn", "joblib", "pandas"}
    or m.startswith(("pravapis.disambiguate", "pravapis.api", "pravapis.cli", "pravapis.metrics")))
srv.shutdown()
print(json.dumps(out, ensure_ascii=False))
"""


def _export(tmp_path: Path) -> Path:
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from export_vercel import export
    finally:
        sys.path.pop(0)
    export(tmp_path)
    return tmp_path


def test_exported_function_serves_requests(tmp_path: Path) -> None:
    out_dir = _export(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-c", DRIVER, str(out_dir / "api")],
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

    status, body, headers = r["n2t"]
    assert status == 200
    assert body["result"] == "Сьнег і сьвет у Эўропе, плян сыстэмы. Ня быў безь мяне."
    assert body["direction"] == "taraskievica"
    assert body["stats"]["by_method"]["model"] == 0
    assert headers["Cache-Control"] == "no-store"
    assert r["t2n"][0] == 200 and r["t2n"][1]["result"] == "Снег і свет"
    assert r["empty"][0] == 200 and r["empty"][1]["result"] == "   "
    assert r["latin"][0] == 422
    assert r["bad_dir"][0] == 400
    assert r["not_str"][0] == 400
    assert r["too_long"][0] == 413
    assert r["bad_json"][0] == 400
    assert r["bad_ctype"][0] == 415
    assert r["get"][0] == 405 and r["get"][2]["Allow"] == "POST, OPTIONS"

    # the vendored copy is what ran, and nothing heavy came along
    assert Path(r["pravapis_file"]).is_relative_to(out_dir / "api" / "_pravapis")
    assert r["loaded"] == []


def test_export_payload_is_small(tmp_path: Path) -> None:
    out_dir = _export(tmp_path)
    total = sum(p.stat().st_size for p in (out_dir / "api").rglob("*") if p.is_file())
    assert total < 2 * 1024 * 1024  # lexicon + rules + stress + code
    names = {p.name for p in (out_dir / "api").rglob("*")}
    assert not names & {"disambiguate", "cli.py", "metrics.py", "main.py", "routes.py"}
    assert (out_dir / "api" / "_pravapis" / "data" / "stress" / "README.md").is_file()  # CC BY-SA
