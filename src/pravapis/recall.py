"""Recall: the changes that should have happened, and why each missing one is missing.

Every other evaluation in this project measures **precision** — of the changes the
converter made, how many were right. None of them can measure recall, because a miss is
a change that should have happened, and there is no list of those. `data/eval/gold.tsv`
cannot supply one: its Taraškievica side was written by applying the same reading of the
norm the converter implements, so a change the converter does not know about is a change
the gold set does not contain either. The blind spots agree.

`data/corpora/parallel.tsv` supplies one from outside: the same article written
independently on be.wikipedia.org and be-tarask.wikipedia.org, aligned sentence by
sentence. Where the two differ token for token, a Taraškievica writer made a change.

## One headline, three declared exclusions

Not every difference between two writers is a change the converter owes. Each attested
difference is sorted by :func:`pravapis.scope.classify_scope` into one of four buckets,
and **only `in_scope` counts for or against the headline**:

``in_scope``            differs only by alternations the converter models. The contract.
``grammatical``         a case or form ending. Збор 2005 is a spelling code and does not
                        legislate declension, so this is outside the contract by the
                        code's own scope — a stated design decision, not a filter.
``reference_deviates``  the be-tarask side contradicts a § of the 2005 code; the
                        converter is right not to reproduce it. Cited per pattern.
``not_orthographic``    the two writers chose different words.

The counts for all four are reported. An exclusion nobody can see is indistinguishable
from a filter tuned until the number looked good, and this project has no way to tell
those apart after the fact either.

## Splits

Recall is measured per split, and the split is **per article**: the same loanword
recurs all through an article, so a sentence-level split would let a stem mined from
train score itself on test. `test` is frozen and read at milestones; mining reads
`train`; `dev` is the one to iterate against.

## Why a miss is missing

An in-scope miss is attributed to the first cause that explains it, which maps onto the
place a fix would go: ``stem_absent``, ``stem_untagged``, ``rule_silent``, ``rule_wrong``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import StrEnum
from pathlib import Path
from typing import Final

from pravapis.lexicon.stems import WordClass
from pravapis.normalize import sanitize
from pravapis.pipeline import Converter
from pravapis.scope import Scope, classify_scope, fold_similarity, format_interval, wilson
from pravapis.tokenize import tokenize
from pravapis.types import Orthography, TokenKind


class MissCause(StrEnum):
    STEM_ABSENT = "stem_absent"
    STEM_UNTAGGED = "stem_untagged"
    RULE_SILENT = "rule_silent"
    RULE_WRONG = "rule_wrong"


@dataclass(frozen=True, slots=True)
class Change:
    """One token pair the two wikis disagree on."""

    source: str  # the Narkamaŭka form
    expected: str  # the Taraškievica form attested opposite it
    sentence: str
    similarity: float  # measured after folding, so orthography costs nothing
    alternations: frozenset[str]
    scope: Scope
    reason: str
    #: which word token of the sentence this is. Conversions are matched to changes by
    #: position, not by spelling: a sentence that repeats a word — and the clitics that
    #: convert differently depending on what follows — would otherwise collapse into one
    #: entry and be scored against the wrong occurrence.
    index: int = -1

    @property
    def in_scope(self) -> bool:
        return self.scope is Scope.IN_SCOPE


@dataclass(frozen=True, slots=True)
class Miss:
    change: Change
    got: str
    cause: MissCause
    detail: str


@dataclass(frozen=True, slots=True)
class RecallReport:
    pairs: int
    articles: int
    tokens: int
    split: str | None
    #: attested differences per bucket
    by_scope: dict[Scope, int] = field(default_factory=dict)
    #: of those, how many the converter reproduced exactly
    hits_by_scope: dict[Scope, int] = field(default_factory=dict)
    misses: list[Miss] = field(default_factory=list)
    false_positives: list[tuple[str, str, str]] = field(default_factory=list)
    by_alternation: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def changes(self) -> int:
        """Every attested difference, in scope or not."""
        return sum(self.by_scope.values())

    @property
    def in_scope(self) -> int:
        return self.by_scope.get(Scope.IN_SCOPE, 0)

    @property
    def in_scope_hits(self) -> int:
        return self.hits_by_scope.get(Scope.IN_SCOPE, 0)

    @property
    def recall(self) -> float:
        """The headline: in-scope changes the converter produced."""
        return self.in_scope_hits / self.in_scope if self.in_scope else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return wilson(self.in_scope_hits, self.in_scope)

    @property
    def by_cause(self) -> dict[MissCause, int]:
        counts = Counter(m.cause for m in self.misses)
        return {cause: counts.get(cause, 0) for cause in MissCause}

    @property
    def wrong_changes(self) -> int:
        """In-scope positions the converter changed and got wrong.

        Distinct from the other misses: ``stem_absent`` and ``rule_silent`` left the
        word alone, which loses recall but costs no precision. Only ``rule_wrong``
        actually put a wrong word on the page.
        """
        return self.by_cause[MissCause.RULE_WRONG]

    @property
    def wrong(self) -> int:
        """Every change the converter made that this corpus says is wrong.

        The two kinds are the same error seen from opposite sides: a change at a
        position where the two wikis agreed (nothing was due), and a change at a
        position where something was due but not this.
        """
        return len(self.false_positives) + self.wrong_changes

    @property
    def precision(self) -> float:
        """Of the changes the converter made *here*, the share that were right.

        The denominator is deliberately not every change the converter made. At a
        position where the attested difference is out of scope — ``экзаменаў`` against
        ``іспытаў``, two different words — converting ``экзаменаў`` to ``экзамэнаў`` is
        correct and will still not match. Counting that as an error would penalise the
        converter for the two wikis' word choices, so only positions the corpus can
        actually adjudicate are scored: the ones where the wikis agree, and the ones
        where they differ in scope.
        """
        made = self.in_scope_hits + self.wrong
        return self.in_scope_hits / made if made else 1.0

    @property
    def precision_interval(self) -> tuple[float, float]:
        return wilson(self.in_scope_hits, self.in_scope_hits + self.wrong)

    def headline(self) -> str:
        return format_interval(self.in_scope_hits, self.in_scope)

    def precision_headline(self) -> str:
        return format_interval(self.in_scope_hits, self.in_scope_hits + self.wrong)


# --- reading the corpus ------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ParallelPair:
    narkamauka: str
    taraskievica: str
    title: str
    similarity: float
    split: str = "train"


def read_parallel(path: Path, split: str | None = None) -> list[ParallelPair]:
    """Rows of the parallel corpus, optionally only those in one split.

    ``split`` is read from the file rather than recomputed. That is what freezes it: a
    change to the hash function, the split shares or the article set cannot silently
    move a sentence from test into train.
    """
    out: list[ParallelPair] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        row_split = parts[7] if len(parts) > 7 else "train"
        if split is not None and row_split != split:
            continue
        out.append(
            ParallelPair(
                sanitize(parts[0]),
                sanitize(parts[1]),
                parts[2] if len(parts) > 2 else "",
                float(parts[6]) if len(parts) > 6 else 0.0,
                row_split,
            )
        )
    return out


# --- what kind of change is this -----------------------------------------------------
_VOWEL_SOFTENERS: Final[dict[str, str]] = {"а": "я", "о": "ё", "у": "ю", "ы": "і"}


def infer_alternations(source: str, expected: str) -> frozenset[str]:
    """Which of the project's alternations would turn ``source`` into ``expected``.

    Read off a character alignment rather than asserted, so a change nobody has modelled
    comes back as ``other`` instead of being quietly filed under something plausible.
    The codes match ``data/lexicon/stems.tsv``: l, i, e, g, eu — plus ``soft`` for
    assimilative softness, which is phonological and not gated on etymology at all.
    """
    a, b = source.lower(), expected.lower()
    if a.startswith(("еў", "еу")) and b.startswith(("эў", "эу")):
        return frozenset({"eu"})
    found: set[str] = set()
    matcher = SequenceMatcher(None, a, b, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue
        old, new = a[i1:i2], b[j1:j2]
        if op == "replace" and len(old) == len(new):
            # A replace block is contiguous, so two adjacent alternations arrive as one
            # opcode: філасофія → філязофія is "ас" → "яз", which is the л alternation
            # and nothing else. Decompose it rather than filing the pair under `other`.
            for k, (old_ch, new_ch) in enumerate(zip(old, new, strict=True)):
                if old_ch != new_ch:
                    found.add(_alternation_of(old_ch, new_ch, a[i1 + k - 1 : i1 + k]))
        elif op in {"insert", "delete"} and (new or old) == "ь":
            found.add("l" if a[i1 - 1 : i1] == "л" else "soft")
        elif "ґ" in old + new:
            found.add("g")
        else:
            found.add("other")
    return frozenset(found)


def _alternation_of(old: str, new: str, previous: str) -> str:
    """Name the alternation that rewrites one character as another."""
    if old == "і" and new == "ы":
        return "i"
    if old == "е" and new == "э":
        return "e"
    if _VOWEL_SOFTENERS.get(old) == new and previous == "л":
        return "l"
    if "ґ" in (old, new):
        return "g"
    return "other"


def form_similarity(source: str, expected: str) -> float:
    """Similarity after folding: two spellings of one word score 1.0."""
    return fold_similarity(source, expected)


def diff_pair(pair: ParallelPair) -> tuple[int, list[Change]]:
    """``(comparable tokens, changes)`` for one aligned sentence pair.

    Only sentences whose word tokens line up one for one are diffed. The aligner already
    required that, but a sentence can still tokenize differently after sanitising, and a
    silent off-by-one would invent changes wholesale.
    """
    n_tokens = [t for t in tokenize(pair.narkamauka) if t.kind is TokenKind.WORD]
    t_tokens = [t for t in tokenize(pair.taraskievica) if t.kind is TokenKind.WORD]
    if len(n_tokens) != len(t_tokens) or not n_tokens:
        return 0, []
    changes: list[Change] = []
    for index, (n, t) in enumerate(zip(n_tokens, t_tokens, strict=True)):
        if n.text.lower() == t.text.lower():
            continue
        scope, reason = classify_scope(n.text, t.text)
        changes.append(
            Change(
                n.text,
                t.text,
                pair.narkamauka,
                form_similarity(n.text, t.text),
                infer_alternations(n.text, t.text),
                scope,
                reason,
                index,
            )
        )
    return len(n_tokens), changes


# --- why an in-scope miss is missing --------------------------------------------------
def classify(change: Change, got: str, converter: Converter) -> Miss:
    """Attribute an in-scope miss to the first cause that explains it."""
    if got.lower() != change.source.lower():
        return Miss(change, got, MissCause.RULE_WRONG, f"produced {got!r}")

    word = change.source.lower()
    needed = {a for a in change.alternations if a in {"l", "i", "e", "g", "eu"}}
    match = converter.engine.stem_match(word, Orthography.TARASKIEVICA)
    in_lexicon = converter.lexicon.lookup(word, Orthography.TARASKIEVICA) is not None

    if needed and match is None:
        if in_lexicon:
            return Miss(change, got, MissCause.RULE_SILENT, "lexicon hit did not change it")
        return Miss(
            change, got, MissCause.STEM_ABSENT, f"no stem covers it; needs {sorted(needed)}"
        )
    if needed and match is not None:
        if match.cls is not WordClass.LOAN:
            return Miss(
                change, got, MissCause.STEM_UNTAGGED, f"stem {match.stem!r} is classed native"
            )
        missing = needed - match.alternations
        if missing:
            return Miss(
                change,
                got,
                MissCause.STEM_UNTAGGED,
                f"stem {match.stem!r} does not license {sorted(missing)}",
            )
        return Miss(
            change, got, MissCause.RULE_SILENT, f"stem {match.stem!r} licenses {sorted(needed)}"
        )
    if in_lexicon:
        return Miss(change, got, MissCause.RULE_SILENT, "lexicon hit did not change it")
    return Miss(change, got, MissCause.RULE_SILENT, f"no rule fired; {sorted(change.alternations)}")


def measure_recall(
    pairs: list[ParallelPair], converter: Converter, split: str | None = None
) -> RecallReport:
    """Convert the Narkamaŭka side and compare its changes with the attested ones."""
    tokens = 0
    by_scope: Counter[Scope] = Counter()
    hits_by_scope: Counter[Scope] = Counter()
    misses: list[Miss] = []
    false_positives: list[tuple[str, str, str]] = []
    by_alternation: dict[str, list[int]] = {}
    used = 0
    articles: set[str] = set()

    for pair in pairs:
        n_tokens, changes = diff_pair(pair)
        if not n_tokens:
            continue
        result = converter.convert(pair.narkamauka, Orthography.TARASKIEVICA)
        if len(result.conversions) != n_tokens:
            # The converter saw a different number of word tokens than the diff did.
            # Scoring by position would then compare the wrong words, so the pair is
            # dropped entirely rather than counted with guessed alignments.
            continue
        used += 1
        tokens += n_tokens
        articles.add(pair.title)
        attested = {c.index for c in changes}

        for change in changes:
            by_scope[change.scope] += 1
            got = result.conversions[change.index].target
            correct = got.lower() == change.expected.lower()
            hits_by_scope[change.scope] += correct
            if not change.in_scope:
                continue
            for code in change.alternations or {"other"}:
                bucket = by_alternation.setdefault(code, [0, 0])
                bucket[0] += correct
                bucket[1] += 1
            if not correct:
                misses.append(classify(change, got, converter))

        # A word the two wikis spell identically needs no change, so a converter that
        # changes it anyway is wrong on this corpus. Same evidence, opposite direction.
        for position, conversion in enumerate(result.conversions):
            if conversion.changed and position not in attested:
                false_positives.append(
                    (conversion.source, conversion.target, str(conversion.rule_id))
                )

    return RecallReport(
        pairs=used,
        articles=len(articles),
        tokens=tokens,
        split=split,
        by_scope={s: by_scope.get(s, 0) for s in Scope},
        hits_by_scope={s: hits_by_scope.get(s, 0) for s in Scope},
        misses=misses,
        false_positives=false_positives,
        by_alternation={k: (v[0], v[1]) for k, v in sorted(by_alternation.items())},
    )


def common_shapes(report: RecallReport, limit: int = 8) -> list[tuple[str, int]]:
    """The most frequent character-level shapes among in-scope misses filed as ``other``.

    ``other`` is the bucket for changes no modelled alternation explains, so it is the
    one place a *missing* alternation would hide. Nothing here changes a number; it says
    what the number is made of.
    """
    shapes: Counter[str] = Counter()
    for miss in report.misses:
        if miss.change.alternations != {"other"}:
            continue
        a, b = miss.change.source.lower(), miss.change.expected.lower()
        edits = [
            f"{a[i1:i2] or '∅'}→{b[j1:j2] or '∅'}"
            for op, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
            if op != "equal"
        ]
        shapes["  ".join(edits)] += 1
    return shapes.most_common(limit)


def write_misses(report: RecallReport, path: Path) -> None:
    """Every in-scope miss, grouped by cause — the work queue this harness exists to produce."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            f"# {len(report.misses)} in-scope miss(es) of {report.in_scope} in-scope changes "
            f"across {report.pairs} aligned sentence pairs"
            + (f" (split: {report.split})" if report.split else "")
            + "\n# cause\tsource\texpected\tgot\talternations\tdetail\tsentence\n"
        )
        for cause in MissCause:
            for miss in (m for m in report.misses if m.cause is cause):
                alternations = ",".join(sorted(miss.change.alternations)) or "-"
                fh.write(
                    f"{cause.value}\t{miss.change.source}\t{miss.change.expected}\t{miss.got}\t"
                    f"{alternations}\t{miss.detail}\t{miss.change.sentence}\n"
                )
