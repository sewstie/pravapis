"""Train data/models/disambig.joblib from data/eval/ambiguous.tsv. Thin wrapper over the CLI."""

from __future__ import annotations

import sys
from pathlib import Path

from pravapis.cli import app

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    args = sys.argv[1:] or [
        str(ROOT / "data" / "eval" / "ambiguous.tsv"),
        "--out",
        str(ROOT / "data" / "models" / "disambig.joblib"),
    ]
    app(["train", *args])
