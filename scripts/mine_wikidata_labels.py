"""Mine loanword stems from Wikidata labels, which are aligned by construction.

    python scripts/mine_wikidata_labels.py --pages 20000

A Wikidata item carries a label in ``be`` and a label in ``be-tarask``. Those two
strings name the same thing and were written by different people under different
orthographies — the alignment problem the sentence corpus spends most of its effort on
is already solved, for free, by the data model. There is no sentence alignment, no
similarity threshold, and no sampling bias from either.

They are also **overwhelmingly proper nouns**, which is exactly where the converter is
weakest: the `e` class (Шапена → Шапэна, Сербіі → Сэрбіі, амерыканскі → амэрыканскі) is
the largest single group of misses, and personal and place names are most of it.

Licensing is simpler too: Wikidata is CC0, so nothing mined here carries the CC BY-SA
attribution obligations the wiki text does.

## What comes out

A **review queue**, not an applied change: ``data/review/stem_candidates.tsv``. Each
row is a proposed stem with the evidence behind it, ranked by how much text it would
actually resolve, and carrying its **blast radius** — the frequent words the stem would
also match, which is where a false positive would come from. Longest-match only protects
against a false friend if a native guard for it already exists, so a candidate that
would catch native vocabulary says so on its own row and the reviewer can add the guard
in the same pass.

Nothing here is applied automatically. The stem inventory is the thing that keeps the
false-positive rate at zero, and it stays hand-reviewed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import regex

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.config import Config  # noqa: E402
from pravapis.metrics import read_negative_set  # noqa: E402
from pravapis.normalize import sanitize  # noqa: E402
from pravapis.pipeline import Converter  # noqa: E402
from pravapis.recall import infer_alternations  # noqa: E402
from pravapis.scope import Scope, classify_scope  # noqa: E402
from pravapis.types import Orthography  # noqa: E402

TARASK_API: Final[str] = "https://be-tarask.wikipedia.org/w/api.php"
WIKIDATA_API: Final[str] = "https://www.wikidata.org/w/api.php"
USER_AGENT: Final[str] = "pravapis-eval/0.1 (https://github.com/sewstie/pravapis; research)"
#: NOT under data/lexicon/stems/. That directory is globbed by
#: pravapis.lexicon.stems.read_stem_sources, and a candidates row has the same first
#: six columns as a stems row, so writing the queue there silently loaded 1,584
#: unreviewed stems into the converter and it began writing *Бэларусь*.
OUT: Final[Path] = ROOT / "data" / "review" / "stem_candidates.tsv"
NEGATIVE: Final[Path] = ROOT / "data" / "eval" / "negative.tsv"

_WORD: Final[regex.Pattern[str]] = regex.compile(r"^[\p{Cyrillic}’ʼ'-]+$")
_ENDINGS: Final[str] = "аяоеуыі"
#: Alternations a stem row may license. `soft` is phonological and needs no stem.
_STEM_ALTERNATIONS: Final[frozenset[str]] = frozenset({"l", "i", "e", "g", "eu"})


@dataclass
class Candidate:
    stem: str
    target: str
    alternations: set[str] = field(default_factory=set)
    examples: list[tuple[str, str]] = field(default_factory=list)
    qids: list[str] = field(default_factory=list)

    #: filled in by ranking
    impact: int = 0
    matched_forms: int = 0
    blast: list[tuple[str, int]] = field(default_factory=list)

    #: filled in by screening against genuine Taraškievica
    verdict: str = "unknown"
    evidence: str = "-"

    #: longer stems this one subsumes, filled in by collapsing
    covers: list[str] = field(default_factory=list)


def _get(api: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"{api}?{urllib.parse.urlencode({**params, 'format': 'json'})}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def walk_qids(pages: int, start: str) -> list[str]:
    """Wikidata ids for be-tarask articles, walked alphabetically 500 at a time."""
    out: list[str] = []
    continue_from: str | None = start
    seen = 0
    while seen < pages and continue_from is not None:
        params = {
            "action": "query",
            "generator": "allpages",
            "gapnamespace": "0",
            "gaplimit": "500",
            "prop": "pageprops",
            "ppprop": "wikibase_item",
            "gapfrom": continue_from,
        }
        data = _get(TARASK_API, params)
        page_map = data.get("query", {}).get("pages", {})
        seen += len(page_map)
        for page in page_map.values():
            qid = (page.get("pageprops") or {}).get("wikibase_item")
            if qid:
                out.append(qid)
        continue_from = (data.get("continue") or {}).get("gapcontinue")
        print(f"  {seen} titles, {len(out)} with a Wikidata id", end="\r", file=sys.stderr)
        time.sleep(0.2)  # be a good API citizen
    return out


def label_pairs(qids: list[str]) -> list[tuple[str, str, str]]:
    """``(qid, be label, be-tarask label)`` for items carrying both."""
    out: list[tuple[str, str, str]] = []
    for i in range(0, len(qids), 50):
        data = _get(
            WIKIDATA_API,
            {
                "action": "wbgetentities",
                "ids": "|".join(qids[i : i + 50]),
                "props": "labels",
                "languages": "be|be-tarask",
            },
        )
        for qid, entity in (data.get("entities") or {}).items():
            labels = entity.get("labels") or {}
            be = (labels.get("be") or {}).get("value")
            tarask = (labels.get("be-tarask") or {}).get("value")
            if be and tarask and be != tarask:
                out.append((qid, sanitize(be), sanitize(tarask)))
        print(f"  {i + 50}/{len(qids)} ids, {len(out)} differing labels", end="\r", file=sys.stderr)
        time.sleep(0.2)
    return out


def stem_of(narkamauka: str, taraskievica: str) -> tuple[str, str] | None:
    """``(Narkamaŭka stem, Taraškievica stem)`` with the shared inflectional ending removed.

    Labels are nominative, so the ending carried here is the nominative one. Dropping it
    when both sides agree on it is what lets an anchored stem match the inflected forms
    that running text is actually made of: ``шапэн`` matches Шапэна, Шапэну, Шапэнам,
    while ``шапэна`` matches only the one form the label happened to be in.
    """
    a, b = narkamauka.lower(), taraskievica.lower()
    if len(a) < 4 or len(b) < 4:
        return None
    if a[-1] == b[-1] and a[-1] in _ENDINGS:
        a, b = a[:-1], b[:-1]
    if a == b or len(a) < 3:
        return None
    return a, b


def mine(rows: list[tuple[str, str, str]]) -> dict[str, Candidate]:
    """Word-align each label pair and propose a stem for every in-scope difference."""
    candidates: dict[str, Candidate] = {}
    for qid, be, tarask in rows:
        be_words, tarask_words = be.split(), tarask.split()
        if len(be_words) != len(tarask_words):
            continue  # a different naming convention, not a respelling
        for n_word, t_word in zip(be_words, tarask_words, strict=True):
            if n_word.lower() == t_word.lower():
                continue
            if not (_WORD.match(n_word) and _WORD.match(t_word)):
                continue
            scope, _ = classify_scope(n_word, t_word)
            if scope is not Scope.IN_SCOPE:
                continue  # a different name, or a case ending: not a stem fact
            alternations = infer_alternations(n_word, t_word) & _STEM_ALTERNATIONS
            if not alternations:
                continue  # pure softness needs no stem
            pair = stem_of(n_word, t_word)
            if pair is None:
                continue
            stem, target = pair
            candidate = candidates.setdefault(stem, Candidate(stem, target))
            candidate.alternations |= alternations
            if len(candidate.examples) < 4:
                candidate.examples.append((n_word, t_word))
            if len(candidate.qids) < 4:
                candidate.qids.append(qid)
    return candidates


def read_frequency(path: Path) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0], int(parts[1])))
    return rows


def rank(candidates: dict[str, Candidate], frequency: list[tuple[str, int]]) -> list[Candidate]:
    """Score each candidate by the tokens it would resolve, and record its blast radius.

    Ranking by class would spend the next review session on whichever alternation is
    fashionable. Ranking by frequency-weighted impact spends it on the stems that change
    the most text: a stem worth four hundred tokens beats one worth three, whatever
    class either belongs to.
    """
    by_prefix: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for form, count in frequency:
        for length in range(3, min(len(form), 12) + 1):
            by_prefix[form[:length]].append((form, count))

    for candidate in candidates.values():
        matches = by_prefix.get(candidate.stem, [])
        candidate.impact = sum(count for _, count in matches)
        candidate.matched_forms = len(matches)
        candidate.blast = sorted(matches, key=lambda kv: -kv[1])[:6]
    return sorted(candidates.values(), key=lambda c: (-c.impact, c.stem))


#: How much more often one spelling must occur in genuine Taraškievica before the corpus
#: is taken to have settled the question. be-tarask is not uniformly Taraškievica, so a
#: handful of unconverted forms is expected and must not refute a good stem; a ratio
#: rather than a count is what stays meaningful across forms of very different frequency.
DECIDING_RATIO: Final[int] = 3
#: Below this many occurrences the corpus has not really seen the word.
MIN_ATTESTATIONS: Final[int] = 5


def screen(candidates: list[Candidate], tarask: dict[str, int]) -> None:
    """Ask 17M tokens of genuine Taraškievica what it actually writes for each blast form.

    Ranking by impact alone puts the *most dangerous* candidates first, because a short
    stem matching native vocabulary has the largest blast radius by construction: `бел`
    (mined from Бела → Бэла) scores 454,828 on the Narkamaŭka list and every one of those
    tokens is беларускі, беларусь, Беларусі. A reviewer working top-down would meet eight
    catastrophic candidates before the first good one.

    The Narkamaŭka frequency list cannot tell those apart — it says how much text a stem
    touches, never whether touching it is right. be-tarask.wikipedia can: if Taraškievica
    writers write `беларусі` 30,000 times and `бэларусі` never, the stem is refuted, and
    no amount of impact redeems it. If they write `амэрыканскі` and not `амерыканскі`,
    it is supported. That is the same evidence the recall harness uses, asked the other
    way round.

    Weak evidence, deliberately treated as weak: an unconverted form on be-tarask looks
    exactly like a refutation, which is why `unknown` is a verdict and not a rejection.
    """
    for candidate in candidates:
        refutes: list[str] = []
        supports: list[str] = []
        for form, _ in candidate.blast:
            if not form.startswith(candidate.stem):
                continue
            produced = candidate.target + form[len(candidate.stem) :]
            n_source, n_target = tarask.get(form, 0), tarask.get(produced, 0)
            if n_source >= MIN_ATTESTATIONS and n_source > n_target * DECIDING_RATIO:
                refutes.append(f"{form}={n_source} vs {produced}={n_target}")
            elif n_target >= MIN_ATTESTATIONS and n_target > n_source * DECIDING_RATIO:
                supports.append(f"{produced}={n_target} vs {form}={n_source}")
        if refutes:
            candidate.verdict = "refuted"
            candidate.evidence = "; ".join(refutes[:3])
        elif supports:
            candidate.verdict = "supported"
            candidate.evidence = "; ".join(supports[:3])
        else:
            candidate.verdict = "unknown"
            candidate.evidence = "-"


#: Review order. Supported first, so the top of the file is work worth doing; refuted
#: last, so the stems that would break Belarusian are the ones nobody has to read.
VERDICT_ORDER: Final[dict[str, int]] = {"supported": 0, "unknown": 1, "refuted": 2}


def breaks_negative_set(stem: str, target: str, negative: Iterable[str]) -> str | None:
    """The first word in the negative set this stem would change, or None.

    The negative set is the list of forms both wikis wrote identically and that the
    corpus never shows converted — so a stem that changes one of them is wrong before
    anybody argues about it. Checking here rather than at the gate is the difference
    between a reviewer reading a row and a reviewer reading a row and a build failure.
    """
    for form in negative:
        if form.startswith(stem) and target + form[len(stem) :] != form:
            return form
    return None


def collapse(candidates: list[Candidate], negative: Iterable[str]) -> list[Candidate]:
    """Fold `амерык`, `амерыкан`, `амерыканск`, `амерыканскі` into one row.

    They are three rows and one fact. Longest match means the shortest stem already
    covers every longer one whose target is just its own target plus the same tail, so
    the extra rows cost review time and buy nothing — and a reviewer who accepts all
    four has written the same rule four times in a file where duplicates are a validation
    error.

    The shortest is not automatically the right one to keep, because a shorter stem
    matches more: `бел` covers `беларускі`. So the row kept is the shortest that is both
    **supported** by the be-tarask screen and **safe against the negative set**, and if
    no member qualifies the group is left alone rather than guessed at. The rows that
    were folded in are named in `covers`, so nothing disappears silently.
    """
    negative = frozenset(negative)
    by_stem = {c.stem: c for c in candidates}
    absorbed: set[str] = set()

    for candidate in sorted(candidates, key=lambda c: len(c.stem)):
        if candidate.stem in absorbed:
            continue
        if candidate.verdict != "supported":
            continue
        if breaks_negative_set(candidate.stem, candidate.target, negative) is not None:
            continue
        tail = candidate.stem, candidate.target
        for other in candidates:
            if other.stem == candidate.stem or other.stem in absorbed:
                continue
            if not other.stem.startswith(tail[0]):
                continue
            # Derivable: the longer stem's target is the shorter one's plus the same
            # extra letters. `амерыканск` -> `амэрыканск` is `амерык` -> `амэрык` with
            # `анск` on the end, so the shorter row already produces it.
            if tail[1] + other.stem[len(tail[0]) :] != other.target:
                continue
            candidate.alternations |= other.alternations
            candidate.covers.append(other.stem)
            absorbed.add(other.stem)

    return [c for c in candidates if c.stem not in absorbed and c.stem in by_stem]


def native_risk(candidate: Candidate, converter: Converter) -> list[str]:
    """Frequent forms the stem would catch that the converter currently leaves alone.

    Longest-match only saves a candidate from a false friend if a native guard already
    exists. These are the words that would start changing the moment the stem is
    accepted, so they are what a reviewer has to look at — and if one of them is
    ordinary Belarusian vocabulary, the guard goes in during the same pass.
    """
    risky: list[str] = []
    for form, _ in candidate.blast:
        match = converter.engine.stem_match(form, Orthography.TARASKIEVICA)
        if match is None and converter.engine.apply(form, Orthography.TARASKIEVICA)[0] == form:
            risky.append(form)
    return risky


COLUMNS = (
    "# stem\tclass\talternations\tsource\tprovenance\ttarget\tverdict\timpact\tforms"
    "\tblast_radius\tevidence\tcovers\texamples"
)

HEADER = (
    COLUMNS
    + """
#
# CANDIDATES, NOT ENTRIES. Proposed loan stems mined from Wikidata labels by
# scripts/mine_wikidata_labels.py. Nothing here is applied: the stem inventory is what
# holds the false-positive rate at zero, and it stays hand-reviewed.
#
# Wikidata labels are aligned by construction — one item, a `be` label and a
# `be-tarask` label — so there is no sentence alignment and no similarity threshold
# here, and no bias from either. Wikidata is CC0.
#
# Only differences that are IN SCOPE (differ solely by modelled alternations) and that
# need a stem (l, i, e, g, eu — not bare softness) become candidates.
#
# verdict       what 17M tokens of genuine be-tarask say about the blast radius:
#                 supported  Taraškievica writes the converted form and not the original
#                 refuted    it writes the ORIGINAL — the stem would corrupt real words
#                 unknown    too rare there to say; read the blast radius yourself
#               Weak evidence, treated as weak: an unconverted form on be-tarask looks
#               exactly like a refutation, so `unknown` rejects nothing.
# impact        tokens in data/corpora/frequency_be.tsv this stem would resolve
# forms         how many distinct forms it matches there
# blast_radius  the most frequent of those forms. THIS IS THE REVIEW COLUMN: longest
#               match only protects against a false friend when a native guard already
#               exists, so if a listed form is ordinary Belarusian vocabulary, add the
#               guard in the same pass. A ! marks forms the converter currently leaves
#               alone — those are what would start changing.
# evidence      the counts behind the verdict, so it can be checked rather than believed.
# covers        longer stems this row makes redundant. They are gone from the file, not
#               rejected: longest match means this row already produces exactly what
#               each of them would. IF YOU DO NOT TRUST THE SHORT STEM, accept the
#               listed longer ones instead — they are narrower and equally attested.
#               `амерык` covers амерыкан, амерыканск, амерыканскі, амерыканска: one
#               fact that was four rows, and four rows a reviewer could accept four
#               times into a file where duplicate stems are a validation error.
#
# Sorted by verdict, then impact. NOT by impact alone: a short stem matching native
# vocabulary has the largest blast radius by construction, so impact order puts the
# most destructive candidates at the top — `бел` from Бела → Бэла scores 454,828, and
# all of it is беларускі, беларусь, Беларусі. Supported first means the top of this
# file is work worth doing.
"""
)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=int, default=20_000, help="be-tarask titles to walk")
    parser.add_argument("--start", default="А", help="alphabetical starting point")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--limit", type=int, default=400, help="candidates to write")
    parser.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="JSON of mined label pairs; read if it exists, written if not. Re-ranking "
        "is then free, which matters because the ranking is the part worth iterating on.",
    )
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if args.cache is not None and args.cache.is_file():
        rows = [tuple(r) for r in json.loads(args.cache.read_text(encoding="utf-8"))]
        print(f"{len(rows)} label pair(s) from {args.cache}")
    else:
        print(f"walking {args.pages} be-tarask titles from {args.start!r}…")
        qids = walk_qids(args.pages, args.start)
        print(f"\n{len(qids)} Wikidata ids")
        rows = label_pairs(qids)
        print(f"\n{len(rows)} items whose be and be-tarask labels differ")
        if args.cache is not None:
            args.cache.parent.mkdir(parents=True, exist_ok=True)
            args.cache.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            print(f"cached → {args.cache}")

    candidates = mine(rows)
    print(f"{len(candidates)} candidate stems before ranking")

    data_dir = Config.default().lexicon.parent
    frequency = read_frequency(data_dir / "corpora" / "frequency_be.tsv")
    converter = Converter.from_config()

    # Drop what the converter already gets right. A queue padded with work already done
    # is a queue nobody finishes, and the impact total at the bottom would count tokens
    # that are already being resolved.
    already = [
        stem
        for stem, candidate in candidates.items()
        if candidate.examples
        and all(
            converter.convert(n, Orthography.TARASKIEVICA).text.lower() == t.lower()
            for n, t in candidate.examples
        )
    ]
    for stem in already:
        del candidates[stem]
    print(f"{len(already)} already handled by the current inventory; {len(candidates)} remain")
    ranked = rank(candidates, frequency)

    tarask_list = data_dir / "corpora" / "frequency_tarask.tsv"
    if tarask_list.is_file():
        tarask = dict(read_frequency(tarask_list))
        screen(ranked, tarask)
        counts = Counter(c.verdict for c in ranked)
        print(
            f"screened against {sum(tarask.values()):,} tokens of genuine Taraškievica: "
            f"{counts['supported']} supported, {counts['unknown']} unknown, "
            f"{counts['refuted']} refuted"
        )
    else:
        # Every row stays `unknown`, which is honest: without the be-tarask counts there
        # is no evidence either way, and a queue that claims otherwise is worse than one
        # that admits it. Rebuild with scripts/build_frequency_list.py.
        print(f"no {tarask_list.name}: every candidate stays 'unknown' and must be read")
    negative = [form for form, _ in read_negative_set(NEGATIVE)] if NEGATIVE.is_file() else []
    before = len(ranked)
    ranked = collapse(ranked, negative)
    print(
        f"collapsed {before - len(ranked)} overlapping row(s) into a shorter stem that "
        f"already covers them; {len(ranked)} remain"
    )
    ranked.sort(key=lambda c: (VERDICT_ORDER[c.verdict], -c.impact, c.stem))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with args.out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(HEADER)
        for candidate in ranked[: args.limit]:
            risky = set(native_risk(candidate, converter))
            blast = " ".join(
                f"{'!' if form in risky else ''}{form}({count})" for form, count in candidate.blast
            )
            examples = " ".join(f"{n}→{t}" for n, t in candidate.examples)
            source = "Wikidata " + ",".join(candidate.qids[:2])
            fh.write(
                f"{candidate.stem}\tloan\t{','.join(sorted(candidate.alternations))}\t{source}\t"
                f"derived\t{candidate.target}\t{candidate.verdict}\t{candidate.impact}\t"
                f"{candidate.matched_forms}\t{blast or '-'}\t{candidate.evidence}\t"
                f"{' '.join(candidate.covers) or '-'}\t{examples}\n"
            )
            written += 1

    print(f"wrote {written} ranked candidates → {args.out}")
    supported = [c for c in ranked[: args.limit] if c.verdict == "supported"]
    covered = sum(c.impact for c in supported)
    print(
        f"the {len(supported)} supported ones would resolve {covered:,} tokens of the "
        "frequency list if all accepted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
