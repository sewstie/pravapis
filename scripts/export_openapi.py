"""Write (or check) the committed OpenAPI schema for the FastAPI service.

    python scripts/export_openapi.py              # regenerate openapi.json
    python scripts/export_openapi.py --check       # fail if it would change

Committed rather than generated on the fly, the same reasoning as
`conformance/cases.jsonl` (`pravapis export-conformance --check`): a schema nobody
diffs is a schema nobody notices changing. Any difference from a run is either a
documented /v2 decision (docs/API.md, "Changing this contract") or a bug — CI runs
this with ``--check`` right after mypy so it fails before anything downstream (the
data checks, the test suite) spends time on a build that was already wrong.

Schema generation only introspects registered routes and Pydantic models — it does
not need a converter, so this never loads the lexicon or rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.api.main import create_app  # noqa: E402

OUT: Path = ROOT / "openapi.json"


def generate() -> dict[str, Any]:
    schema: dict[str, Any] = create_app().openapi()
    return schema


def render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if openapi.json is not what this run produces"
    )
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    rendered = render(generate())

    if args.check:
        if not args.out.is_file():
            print(f"{args.out} does not exist; run without --check to create it")
            return 1
        current = args.out.read_text(encoding="utf-8")
        if current != rendered:
            print(
                f"{args.out} is stale — the FastAPI service's routes or schemas changed "
                "without regenerating it.\n"
                "  python scripts/export_openapi.py\n"
                'If the change is deliberate, docs/API.md, "Changing this contract" says '
                "what kind of version bump it needs."
            )
            return 1
        print(f"ok — {args.out} matches the current schema")
        return 0

    args.out.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
