"""Build a Narkamaŭka word-form frequency list from the be.wikipedia dump.

    python scripts/build_frequency_list.py --dump bewiki-20260901-pages-articles.xml.bz2

Coverage has to be measured against the forms Belarusian text is actually made of, not
against the forms the project happened to think of, and the ranking that decides which
stem to add next is only as good as the counts behind it.

The dump rather than the API: it is one reproducible file with a date in its name, it is
free of rate limits and sampling, and it contains the whole encyclopedia rather than
whatever ``generator=random`` happened to return. An API sample also cannot be
re-derived — run it twice and you get two different lists, so a coverage figure computed
from one is not checkable against the other.

The dump is streamed and decompressed in memory: nothing is written to disk but the
counts, and memory stays flat regardless of dump size.

Wikitext is stripped crudely — templates, links, refs, tables — because the alternative
is a parser, and for counting word forms the residue of a crude strip is noise that
falls off the end of the list rather than error that moves the head of it.

Output: data/corpora/frequency_be.tsv — ``form<TAB>count``, most frequent first.
"""

from __future__ import annotations

import argparse
import bz2
import html
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import regex

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pravapis.normalize import sanitize  # noqa: E402

OUT: Final[Path] = ROOT / "data" / "corpora" / "frequency_be.tsv"

_WORD: Final[regex.Pattern[str]] = regex.compile(r"[\p{Cyrillic}’ʼ'-]+")
_TEXT_OPEN: Final[regex.Pattern[str]] = regex.compile(r"<text\b[^>]*>")
_TEXT_CLOSE: Final[str] = "</text>"
_TITLE: Final[regex.Pattern[str]] = regex.compile(r"<title>([^<]*)</title>")
_REDIRECT: Final[regex.Pattern[str]] = regex.compile(r"<redirect\b")
_NS: Final[regex.Pattern[str]] = regex.compile(r"<ns>(\d+)</ns>")

#: Wikitext constructs whose *contents* are markup rather than prose.
_STRIP: Final[tuple[regex.Pattern[str], ...]] = tuple(
    regex.compile(p, regex.DOTALL)
    for p in (
        r"<ref[^>]*/>",
        r"<ref.*?</ref>",
        r"<!--.*?-->",
        r"<math.*?</math>",
        r"\{\{[^{}]*\}\}",  # templates, innermost first (applied repeatedly)
        r"\{\|.*?\|\}",  # tables
        r"\[\[[Ff]ile:.*?\]\]",
        r"\[\[[Іі]мідж:.*?\]\]",
        r"\[\[[Вв]ыява:.*?\]\]",
        r"<[^>]+>",  # any remaining tag
    )
)
_LINK_TARGET: Final[regex.Pattern[str]] = regex.compile(r"\[\[(?:[^\]|]*\|)?([^\]|]*)\]\]")
_APOSTROPHES: Final[regex.Pattern[str]] = regex.compile(r"'{2,}")


def strip_wikitext(text: str) -> str:
    for _ in range(4):  # templates nest; a few passes clear the common depths
        before = text
        for pattern in _STRIP:
            text = pattern.sub(" ", text)
        if text == before:
            break
    text = _LINK_TARGET.sub(r"\1", text)
    return _APOSTROPHES.sub("", text)


def iter_article_text(path: Path, exclude: frozenset[str] = frozenset()) -> Iterator[str]:
    """Yield the wikitext of every main-namespace, non-redirect article in the dump.

    ``exclude`` drops articles by title. That exists because this list is not only
    descriptive: the be-tarask list decides which mined stems are believed, so if it counted
    the articles the recall corpus holds out, a stem would be accepted partly on the
    evidence of the sentences it is later scored against. Excluding them keeps the test
    split a test split.
    """
    with bz2.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        namespace, redirect, collecting = None, False, False
        title: str | None = None
        buffer: list[str] = []
        for line in fh:
            if not collecting:
                if "<page>" in line:
                    namespace, redirect, title = None, False, None
                if (m := _TITLE.search(line)) is not None:
                    title = html.unescape(m.group(1))
                if (m := _NS.search(line)) is not None:
                    namespace = int(m.group(1))
                if _REDIRECT.search(line):
                    redirect = True
                if (m := _TEXT_OPEN.search(line)) is not None:
                    if namespace != 0 or redirect or (title is not None and title in exclude):
                        continue
                    rest = line[m.end() :]
                    if _TEXT_CLOSE in rest:
                        yield rest.split(_TEXT_CLOSE, 1)[0]
                    else:
                        collecting, buffer = True, [rest]
            else:
                if _TEXT_CLOSE in line:
                    buffer.append(line.split(_TEXT_CLOSE, 1)[0])
                    collecting = False
                    yield "".join(buffer)
                    buffer = []
                else:
                    buffer.append(line)


def main(argv: list[str]) -> int:
    # Before parse_args: --help prints the docstring and the defaults, both of which
    # contain ŭ, and the Windows console is cp1252 until told otherwise.
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, required=True, help="bewiki pages-articles .xml.bz2")
    parser.add_argument("--top", type=int, default=20_000)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--max-articles", type=int, default=0, help="0 = the whole dump")
    parser.add_argument(
        "--label",
        default="Narkamaŭka",
        help="orthography named in the header; the stripper is language-agnostic",
    )
    parser.add_argument(
        "--wiki",
        default="be.wikipedia.org",
        help="wiki named in the CC BY-SA attribution line",
    )
    parser.add_argument(
        "--exclude-titles",
        type=Path,
        default=None,
        help="file of article titles, one per line, to leave out of the counts",
    )
    args = parser.parse_args(argv)

    exclude: frozenset[str] = frozenset()
    if args.exclude_titles is not None:
        exclude = frozenset(
            line.strip()
            for line in args.exclude_titles.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        print(f"excluding {len(exclude)} held-out article(s)")

    counts: Counter[str] = Counter()
    articles = 0
    for wikitext in iter_article_text(args.dump, exclude):
        articles += 1
        for word in _WORD.findall(sanitize(strip_wikitext(wikitext))):
            if len(word) > 1:
                counts[word.lower()] += 1
        if articles % 5000 == 0:
            print(f"  {articles} articles, {len(counts)} forms", file=sys.stderr)
        if args.max_articles and articles >= args.max_articles:
            break

    ranked = counts.most_common(args.top)
    total = sum(counts.values())
    kept = sum(c for _, c in ranked)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            f"# form<TAB>count — {args.label} word-form frequency, most frequent first.\n"
            f"# Built by scripts/build_frequency_list.py from {args.dump.name}:\n"
            f"# {articles} main-namespace articles, {len(counts)} distinct forms over\n"
            f"# {total} tokens; top {len(ranked)} kept, covering {kept / total:.1%} of tokens.\n"
            "# Wikitext is stripped crudely, so the tail contains markup residue; the head,\n"
            "# which is what the coverage figure and the mining rank depend on, does not.\n"
            + (
                f"# {len(exclude)} article(s) held out by the recall corpus are EXCLUDED,\n"
                "# so a stem is never believed partly on the evidence of the sentences\n"
                "# it is later scored against.\n"
                if exclude
                else ""
            )
            + f"# Text is CC BY-SA 4.0 ({args.wiki}).\n"
        )
        for form, count in ranked:
            fh.write(f"{form}\t{count}\n")

    print(
        f"{articles} articles → {len(counts)} distinct forms over {total} tokens; "
        f"wrote top {len(ranked)} ({kept / total:.1%} of tokens) → {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
