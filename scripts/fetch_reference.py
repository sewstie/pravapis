"""Fetch the normative sources both orthographies are cited against.

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

Two codifications, because the converter has two sides and each is answerable to its
own authority:

* **Taraškievica** — Збор правілаў 2005, the PDF from pravapis.org via the Wayback
  Machine. Cited as `Збор правілаў 2005, §N`.
* **Narkamaŭka** — Правілы беларускай арфаграфіі і пунктуацыі (2008), the rules
  attached to Закон № 420-З. Cited as `Правілы 2008, §N`.

The 2008 rules come from Belarusian Wikisource, pinned to a revision id, because
pravo.by and etalonline.by are not resolvable from every build machine and neither
publishes a stable hashed artefact. That makes it a **transcription, not the official
act** — recorded as such in data/reference/README.md. A citation taken from it should
be spot-checked against pravo.by where that is reachable.

Nothing is redistributed. This downloads to a git-ignored directory, for reading.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR: Final[Path] = ROOT / "data" / "reference"
PDF: Final[Path] = OUT_DIR / "pravapis2005.pdf"
TXT: Final[Path] = OUT_DIR / "pravapis2005.txt"
RULES2008: Final[Path] = OUT_DIR / "pravily2008.txt"

URL: Final[str] = (
    "https://web.archive.org/web/20051224051023/http://pravapis.org:80/pravapis2005.pdf"
)
SHA256: Final[str] = "974058bc10cf6db380b3a2cd51d3f0417fad2283d18446542817db2f9e90b1fe"
USER_AGENT: Final[str] = "pravapis-eval/0.1 (https://github.com/sewstie/pravapis; research)"

#: Belarusian Wikisource, pinned. The revision is part of the citation: the page is
#: editable, and a §-number read off a different revision is a different claim.
WIKISOURCE_API: Final[str] = "https://be.wikisource.org/w/api.php"
RULES2008_TITLE: Final[str] = (
    "Закон Рэспублікі Беларусь «Аб Правілах беларускай арфаграфіі і пунктуацыі»"
)
RULES2008_REVID: Final[int] = 283776
RULES2008_SHA256: Final[str] = "286c03e0c4d92bc6f440ee55c308f8c2ca7d13ed89b6e83b97e0261ca5cc79a0"


def fetch_rules_2008() -> int:
    """The 2008 Narkamaŭka rules, pinned to one Wikisource revision."""
    if RULES2008.is_file():
        digest = hashlib.sha256(RULES2008.read_bytes()).hexdigest()
        if digest == RULES2008_SHA256:
            print(f"{RULES2008.name}: already present, sha256 verified")
            return 0
        print(f"{RULES2008.name}: present but sha256 differs — refetching")

    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "revids": str(RULES2008_REVID),
        "format": "json",
    }
    url = f"{WIKISOURCE_API}?{urllib.parse.urlencode(params)}"
    print(f"downloading {RULES2008_TITLE} (revid {RULES2008_REVID})")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)

    pages = (payload.get("query") or {}).get("pages") or {}
    if not pages:
        print("no such revision — the page may have been deleted or renamed")
        return 1
    page = next(iter(pages.values()))
    if page.get("title") != RULES2008_TITLE:
        print(f"revid {RULES2008_REVID} is on {page.get('title')!r}, not the expected page")
        return 1
    text = page["revisions"][0]["slots"]["main"]["*"]

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if digest != RULES2008_SHA256:
        print("HASH MISMATCH")
        print(f"  expected {RULES2008_SHA256}")
        print(f"  got      {digest}")
        print("A pinned revision cannot change, so this is a different page. Not writing.")
        return 1

    RULES2008.write_text(text, encoding="utf-8")
    print(f"{RULES2008.name}: {len(text):,} chars, sha256 verified")
    print()
    print("The rules are numbered '§ 15.' in the attached Правілы. Cite them as")
    print("'Правілы 2008, §N' — the Narkamaŭka counterpart of 'Збор правілаў 2005, §N'.")
    return 0


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
    return fetch_rules_2008()


if __name__ == "__main__":
    raise SystemExit(main())
