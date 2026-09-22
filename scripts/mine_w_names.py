"""Mine the W-name inventory from Wikidata, where the evidence is already aligned.

    python scripts/mine_w_names.py                 # rewrite data/names/w_names.tsv
    python scripts/mine_w_names.py --dry-run       # print what would be written

## The question this answers

Belarusian writes Ў at the start of a name to render English *W* — *Ўіл*, *Ўотэрз*,
*Ўэйлз*. Збор 2005 §18 also turns an unstressed initial У into Ў after a vowel. After a
vowel the two are indistinguishable: *школу Ўайлд* could be either, and Narkamaŭka keeps
the Ў in the name while undoing it in the §18 case. So `initial_w_to_u` needs to know
which Ў-words are names, and no rule can tell it — it is a fact about a word, not a
pattern in it.

## Why Wikidata settles it

A Wikidata item carries a label in `en` and a label in `be-tarask`, written by different
people, naming the same thing. An item whose English label starts with **W** and whose
be-tarask label starts with **Ў** is a W-name by construction: two independent editors
agreed on the correspondence, and nothing about the Belarusian spelling had to be
guessed. Wikidata is CC0, so nothing mined here carries an attribution obligation.

Ў never begins a native Belarusian word, which is what makes the be-tarask side of this
query so clean: a title starting with Ў is almost always a borrowed name already.

## What comes out

`data/names/w_names.tsv`, stems with their evidence. The hand-listed entries — the
ones found in `data/eval/tarask/gold_t2n.tsv` when the question first came up — are kept
and tagged `hand`, because they were verified against attested sentences rather than a
label pair, and that is a stronger warrant, not a weaker one.

Stems, not forms: matching is by prefix, so `ўотэрз` covers *Ўотэрзам* and `ўіл` covers
*Ўіла*. The first word of the label is taken — *Ўэйлз* out of *Ўэйлзу*, *Ўіл* out of
*Ўіл Гантынг* — because the rest of a multi-word name is matched on its own token.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.normalize import sanitize  # noqa: E402
from pravapis.rules.w_names import WNameEntry, read_w_names  # noqa: E402

OUT: Final[Path] = ROOT / "data" / "names" / "w_names.tsv"

TARASK_API: Final[str] = "https://be-tarask.wikipedia.org/w/api.php"
WIKIDATA_API: Final[str] = "https://www.wikidata.org/w/api.php"
USER_AGENT: Final[str] = "pravapis-eval/0.1 (https://github.com/sewstie/pravapis; research)"

HEADER = """\
#!schema tag:pravapis,2026:schema:w_names:1
#!columns stem\tprovenance\tevidence
# stem<TAB>provenance<TAB>evidence
#
# Names whose initial Ў renders English W, not Збор 2005 §18's alternation of у.
#
# §18 turns an unstressed initial У into Ў after a vowel, and T -> N undoes it. But
# Belarusian also writes Ў at the start of a name for English W, and Narkamaŭka keeps
# that Ў. After a vowel the two are indistinguishable — `школу Ўайлд` could be either —
# so reversing a name would corrupt it. This file is the list of words where the Ў
# stays. See data/NORMS.md, rule morph.initial_u_w.
#
# Matching is by prefix on the lowercased word, so a stem covers the whole paradigm:
# `ўотэрз` matches Ўотэрзам, `ўіл` matches Ўіла.
#
# stem        lowercased, always begins with ў
# provenance  hand     = read off an attested sentence in data/eval/tarask/gold_t2n.tsv
#             wikidata = an item whose en label starts with W and be-tarask label with Ў
# evidence    the gold file for `hand`; `QID en-label` for `wikidata`
#
# Regenerate with `python scripts/mine_w_names.py`. Hand rows are preserved verbatim;
# the list is open-ended by nature and a name nobody has written down yet will still
# come back from T -> N with У. That limit is recorded in data/NORMS.md, not hidden.
"""


def _get(api: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"{api}?{urllib.parse.urlencode({**params, 'format': 'json'})}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def walk_w_qids(limit: int) -> list[str]:
    """Wikidata ids for every be-tarask article whose title begins with Ў."""
    out: list[str] = []
    continue_from: str | None = None
    while len(out) < limit:
        params = {
            "action": "query",
            "generator": "allpages",
            "gapnamespace": "0",
            "gaplimit": "500",
            "gapprefix": "Ў",
            "prop": "pageprops",
            "ppprop": "wikibase_item",
        }
        if continue_from is not None:
            params["gapcontinue"] = continue_from
        data = _get(TARASK_API, params)
        pages = (data.get("query") or {}).get("pages") or {}
        for page in pages.values():
            qid = (page.get("pageprops") or {}).get("wikibase_item")
            if qid:
                out.append(qid)
        print(f"  {len(out)} Ў-titles with a Wikidata id", end="\r", file=sys.stderr)
        continue_from = (data.get("continue") or {}).get("gapcontinue")
        if continue_from is None:
            break
        time.sleep(0.2)  # be a good API citizen
    print(file=sys.stderr)
    return out


def w_name_pairs(qids: list[str]) -> list[tuple[str, str, str]]:
    """``(qid, en label, be-tarask label)`` where en starts with W and be-tarask with Ў."""
    out: list[tuple[str, str, str]] = []
    for i in range(0, len(qids), 50):
        data = _get(
            WIKIDATA_API,
            {
                "action": "wbgetentities",
                "ids": "|".join(qids[i : i + 50]),
                "props": "labels",
                "languages": "en|be-tarask",
            },
        )
        for qid, entity in (data.get("entities") or {}).items():
            labels = entity.get("labels") or {}
            english = (labels.get("en") or {}).get("value") or ""
            tarask = (labels.get("be-tarask") or {}).get("value") or ""
            if english[:1].upper() == "W" and sanitize(tarask)[:1] == "Ў":
                out.append((qid, english, sanitize(tarask)))
        print(
            f"  {min(i + 50, len(qids))}/{len(qids)} ids, {len(out)} W-names",
            end="\r",
            file=sys.stderr,
        )
        time.sleep(0.2)
    print(file=sys.stderr)
    return out


def stem_of(label: str) -> str:
    """The first word of the label, lowercased — the part a prefix match needs."""
    return label.split()[0].strip("«»\"'(),.").lower()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5000, help="max Ў-titles to walk")
    parser.add_argument("--dry-run", action="store_true", help="print, write nothing")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    existing = read_w_names(OUT) if OUT.is_file() else []
    hand = [row for row in existing if row.provenance == "hand"]

    qids = walk_w_qids(args.limit)
    pairs = w_name_pairs(qids)

    mined: dict[str, WNameEntry] = {}
    for qid, english, tarask in pairs:
        stem = stem_of(tarask)
        if not stem.startswith("ў") or len(stem) < 3:
            continue
        # Shortest stem wins: two items naming the same person (Ўотэрз, Ўотэрзам)
        # should leave one row that covers both.
        if stem not in mined or len(stem) < len(mined[stem].stem):
            mined[stem] = WNameEntry(stem=stem, provenance="wikidata", evidence=f"{qid} {english}")

    # A hand row always wins: it was read off an attested sentence.
    by_stem = {row.stem: row for row in hand}
    for stem, row in sorted(mined.items()):
        if any(stem.startswith(h) for h in by_stem):
            continue
        by_stem[stem] = row

    rows = sorted(by_stem.values(), key=lambda r: (r.provenance != "hand", r.stem))
    payload = HEADER + "\n".join(f"{r.stem}\t{r.provenance}\t{r.evidence}" for r in rows) + "\n"

    print(f"{len(hand)} hand, {len(mined)} mined, {len(rows)} rows total")
    for row in rows:
        print(f"  {row.stem:<16} {row.provenance:<9} {row.evidence}")
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    OUT.write_bytes(payload.encode("utf-8"))
    print(f"\n{OUT}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
