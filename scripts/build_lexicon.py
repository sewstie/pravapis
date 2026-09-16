"""Compile data/lexicon/*.tsv into data/lexicon.marisa. Thin wrapper over the CLI."""

from __future__ import annotations

import sys
from pathlib import Path

from pravapis.cli import app

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    args = sys.argv[1:] or [
        str(ROOT / "data" / "lexicon"),
        "--out",
        str(ROOT / "data" / "lexicon.marisa"),
    ]
    app(["build-lexicon", *args])
