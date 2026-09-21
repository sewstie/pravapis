"""Fetch the 2005 codification from the Wayback Machine and extract its text.

    python scripts/fetch_reference.py

The book is copyrighted and `data/reference/` is git-ignored, so a fresh checkout has no
copy of the source every rule in `data/NORMS.md` cites. That is not a small gap: a rule
that cannot be checked against the text does not get written, so the whole ў question sat
unimplemented — and was logged against the wrong section, §15 instead of §18 — for want
of forty seconds of downloading.

The URL and the SHA-256 come from `data/reference/README.md`, which recorded them when
the file was first obtained. The hash is checked, not trusted: a Wayback capture is a
copy of something someone else served, and a silently different edition would change what
the citations mean.

Nothing is redistributed. This downloads to a git-ignored directory, for reading.
"""

from __future__ import annotations

import hashlib
import re
import sys
import urllib.request
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR: Final[Path] = ROOT / "data" / "reference"
PDF: Final[Path] = OUT_DIR / "pravapis2005.pdf"
TXT: Final[Path] = OUT_DIR / "pravapis2005.txt"

URL: Final[str] = (
    "https://web.archive.org/web/20051224051023/http://pravapis.org:80/pravapis2005.pdf"
)
SHA256: Final[str] = "974058bc10cf6db380b3a2cd51d3f0417fad2283d18446542817db2f9e90b1fe"
USER_AGENT: Final[str] = "pravapis-eval/0.1 (https://github.com/sewstie/pravapis; research)"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not PDF.is_file():
        print(f"downloading {URL}")
        request = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=300) as response:
            PDF.write_bytes(response.read())

    digest = hashlib.sha256(PDF.read_bytes()).hexdigest()
    if digest != SHA256:
        print(f"HASH MISMATCH\n  expected {SHA256}\n  got      {digest}")
        print("This is not the edition data/reference/README.md records. Not extracting.")
        return 1
    print(f"{PDF.name}: {PDF.stat().st_size:,} bytes, sha256 verified")

    try:
        from pypdf import PdfReader
    except ImportError:
        print("\nInstall pypdf to extract the text: pip install pypdf")
        print("(not a project dependency — only this script needs it)")
        return 1

    reader = PdfReader(PDF)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    TXT.write_text(re.sub(r"[ \t]+", " ", text), encoding="utf-8")
    print(f"{TXT.name}: {len(reader.pages)} pages, {len(text):,} chars")
    print(
        "\nThe book numbers its rules plainly — '18.', '20.' — not '§18'. Search for the\n"
        "chapter headings ('Разьдзел 6. ПРАВАПІС У – Ў') when a rule number is not enough."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
