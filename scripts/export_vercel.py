"""Assemble the Vercel function for the Paznaj Next.js repo.

    python scripts/export_vercel.py OUT_DIR [--force]

OUT_DIR is the Paznaj repository root (or any directory, for a dry run).
Writes:

    OUT_DIR/
      requirements.txt              pinned runtime deps (refuses to overwrite without --force)
      api/
        convert.py                  the function: POST /api/convert
        _belnorm/                   vendored, not a function (leading underscore)
          belnorm/                  runtime subset of the package
          data/
            lexicon.marisa          compiled from data/lexicon/*.tsv
            rules/*.yaml
            stress/                 GrammarDB first-stress tables + CC BY-SA attribution
          VERSION                   belnorm git commit the copy was made from

Left out on purpose: the FastAPI app, the CLI, metrics, and the experimental
disambiguate/ package (no [ml] extra, no BelVoice data). Prints a size report.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "belnorm"
DATA = ROOT / "data"
DEPLOY = ROOT / "deploy" / "vercel"

RUNTIME_MODULES = (
    "__init__.py",
    "types.py",
    "casing.py",
    "config.py",
    "normalize.py",
    "tokenize.py",
    "pipeline.py",
    "stress.py",
    "webapi.py",
    "rules/__init__.py",
    "rules/engine.py",
    "rules/loanwords.py",
    "rules/morphology.py",
    "rules/palatalization.py",
    "lexicon/__init__.py",
    "lexicon/store.py",
    "lexicon/case_forms.py",
    "lexicon/builder.py",
)
STRESS_FILES = ("first_stressed.marisa", "proper_first_stressed.marisa", "SOURCE", "README.md")


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _commit() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        dirty = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain", "--", "src", "data", "deploy"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def export(out: Path, *, force: bool = False) -> dict[str, int]:
    sys.path.insert(0, str(ROOT / "src"))
    from belnorm.lexicon.builder import build_from_sources, save_lexicon, sources_digest

    api = out / "api"
    vendor = api / "_belnorm"
    req = out / "requirements.txt"
    if (
        req.exists()
        and not force
        and req.read_bytes() != (DEPLOY / "requirements.txt").read_bytes()
    ):
        raise SystemExit(f"{req} exists and differs; merge by hand or pass --force")
    if vendor.exists():
        shutil.rmtree(vendor)

    for rel in RUNTIME_MODULES:
        dst = vendor / "belnorm" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SRC / rel, dst)

    (vendor / "data" / "rules").mkdir(parents=True)
    for yml in sorted((DATA / "rules").glob("*.yaml")):
        shutil.copy2(yml, vendor / "data" / "rules" / yml.name)
    (vendor / "data" / "stress").mkdir(parents=True)
    for name in STRESS_FILES:
        shutil.copy2(DATA / "stress" / name, vendor / "data" / "stress" / name)
    shutil.copytree(DATA / "lexicon" / "case", vendor / "data" / "lexicon" / "case")
    fwd, rev = build_from_sources(DATA / "lexicon")
    save_lexicon(
        fwd, rev, vendor / "data" / "lexicon.marisa", source_digest=sources_digest(DATA / "lexicon")
    )
    (vendor / "VERSION").write_text(_commit() + "\n", encoding="utf-8")

    shutil.copy2(DEPLOY / "api" / "convert.py", api / "convert.py")
    shutil.copy2(DEPLOY / "requirements.txt", req)

    return {
        "handler": _size(api / "convert.py"),
        "code": _size(vendor / "belnorm"),
        "lexicon": _size(vendor / "data" / "lexicon.marisa"),
        "rules": _size(vendor / "data" / "rules"),
        "stress": _size(vendor / "data" / "stress"),
        "total": _size(api),
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--force", action="store_true", help="overwrite a different requirements.txt")
    args = ap.parse_args(argv)
    sizes = export(args.out, force=args.force)
    print(f"exported to {args.out}")
    for k, v in sizes.items():
        print(f"  {k:<8} {v / 1024:9.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
