"""Legacy Python API development server; the website uses serve_website.mjs instead.

    python scripts/serve_local.py [--port 3000]

A stand-in for `vercel dev` with no account or Node toolchain: same handler
class, same static files. Not for production.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def load_function() -> Any:
    spec = importlib.util.spec_from_file_location(
        "convert_fn", ROOT / "deploy" / "vercel" / "standalone" / "convert.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.handler


def make_handler() -> type[SimpleHTTPRequestHandler]:
    fn = load_function()

    class Local(SimpleHTTPRequestHandler):
        def _route(self) -> bool:
            if self.path.split("?", 1)[0] == "/api/convert":
                fn._dispatch(self)  # reuse the function's handler logic on this request
                return True
            return False

        def do_POST(self) -> None:
            if not self._route():
                self.send_error(404)

        def do_OPTIONS(self) -> None:
            if not self._route():
                self.send_error(404)

        def do_GET(self) -> None:
            if not self._route():
                super().do_GET()

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write(f"{self.command} {self.path}\n")

    return partial(Local, directory=str(ROOT / "public"))  # type: ignore[return-value]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--port", type=int, default=3000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), make_handler())
    print(f"serving http://{args.host}:{args.port}/  (Ctrl+C to stop)")
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
