"""Recall: the changes that should have happened, and why each missing one is missing.

Every other evaluation in this project measures **precision** — of the changes the
converter made, how many were right. None of them can measure recall, because a miss is
a change that should have happened, and there is no list of those. `data/eval/gold.tsv`
cannot supply one: its Taraškievica side was written by applying the same reading of the
norm the converter implements, so a change the converter does not know about is a change
the gold set does not contain either. The blind spots agree.

`data/corpora/parallel.tsv` supplies one from outside: the same article written
independently on be.wikipedia.org and be-tarask.wikipedia.org, aligned sentence by
sentence. Where the two differ token for token, a Taraškievica writer made a change the
converter is supposed to make.

## Two numbers, not one

A differing token pair is evidence of a difference, not proof that the difference is
orthographic. The two wikis also make different word choices — `плошчы` / `пляцы`,
`годзе` / `року` — and no converter should "fix" those. So this reports a **bound**:

* **strict recall** counts every diff as a change that should have happened. It is a
  lower bound: vocabulary differences the converter rightly ignores count against it.
* **orthographic recall** counts only diffs that look like a spelling of the same word
  (character similarity above a threshold). It is an upper bound: a genuine miss whose
  Taraškievica form is very different — a lexicon gap like `Германія` / `Нямеччына` —
  is excluded along with the noise.

The truth is between them. Reporting one number would require deciding, silently and
without evidence, which kind of error to make.

## Why a miss is missing

Each miss is attributed to the first of these that explains it, which maps onto the
places a fix would go:

``stem_absent``     the word matches no stem in the inventory and no lexicon entry, so
                    nothing could have told the rules it was a borrowing
``stem_untagged``   a stem matched, but it is classed ``native`` or does not license the
                    alternation this change needs — the fact is there and wrong
``rule_silent``     the etymology was available and no rule changed the word
``rule_wrong``      a rule fired and produced something other than the attested form
``not_orthographic`` the two forms are not a spelling of the same word (reported, never
                    counted as a converter failure)
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
from pravapis.tokenize import tokenize
from pravapis.types import Orthography, TokenKind

#: Character similarity above which two forms are taken to be spellings of one word.
#: Calibrated against the corpus, not chosen a priori: see `pravapis eval --recall`,
#: which prints the distribution either side of it so the cut can be argued with.
ORTHOGRAPHIC_SIMILARITY: Final[float] = 0.7


class MissCause(StrEnum):
    STEM_ABSENT = "stem_absent"
    STEM_UNTAGGED = "stem_untagged"
    RULE_SILENT = "rule_silent"
    RULE_WRONG = "rule_wrong"
    NOT_ORTHOGRAPHIC = "not_orthographic"


@dataclass(frozen=True, slots=True)
class Change:
    """One token pair the two wikis disagree on: a change that should happen."""

    source: str  # the Narkamaŭka form
    expected: str  # the Taraškievica form attested opposite it
    sentence: str
    similarity: float
    alternations: frozenset[str]

    @property
    def orthographic(self) -> bool:
        return self.similarity >= ORTHOGRAPHIC_SIMILARITY


@dataclass(frozen=True, slots=True)
class Miss:
    change: Change
    got: str
    cause: MissCause
    detail: str


@dataclass(frozen=True, slots=True)
class RecallReport:
    pairs: int
    tokens: int
    changes: int
    orthographic_changes: int
    hits: int
    orthographic_hits: int
    misses: list[Miss] = field(default_factory=list)
    false_positives: list[tuple[str, str, str]] = field(default_factory=list)
    by_alternation: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def strict_recall(self) -> float:
        return self.hits / self.changes if self.changes else 0.0

    @property
    def orthographic_recall(self) -> float:
        return (
            self.orthographic_hits / self.orthographic_changes if self.orthographic_changes else 0.0
        )

    @property
    def by_cause(self) -> dict[MissCause, int]:
        counts = Counter(m.cause for m in self.misses)
        return {cause: counts.get(cause, 0) for cause in MissCause}


# --- reading the corpus ------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ParallelPair:
    narkamauka: str
    taraskievica: str
    title: str
    similarity: float


def read_parallel(path: Path) -> list[ParallelPair]:
    """``narkamauka<TAB>taraskievica<TAB>title_be<TAB>…`` rows; ``#`` comments skipped."""
    out: list[ParallelPair] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        similarity = float(parts[6]) if len(parts) > 6 else 0.0
        out.append(
            ParallelPair(
                sanitize(parts[0]),
                sanitize(parts[1]),
                parts[2] if len(parts) > 2 else "",
                similarity,
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
    return SequenceMatcher(None, source.lower(), expected.lower(), autojunk=False).ratio()


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
    for n, t in zip(n_tokens, t_tokens, strict=True):
        if n.text.lower() == t.text.lower():
            continue
        changes.append(
            Change(
                n.text,
                t.text,
                pair.narkamauka,
                form_similarity(n.text, t.text),
                infer_alternations(n.text, t.text),
            )
        )
    return len(n_tokens), changes


# --- why a miss is missing -----------------------------------------------------------
def classify(change: Change, got: str, converter: Converter) -> Miss:
    """Attribute a miss to the first cause that explains it."""
    if not change.orthographic:
        return Miss(change, got, MissCause.NOT_ORTHOGRAPHIC, "forms are not one word")
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
            change,
            got,
            MissCause.STEM_ABSENT,
            f"no stem covers it; needs {sorted(needed) or ['?']}",
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
    # Softness and everything else: no etymology needed, so nothing fired.
    if in_lexicon:
        return Miss(change, got, MissCause.RULE_SILENT, "lexicon hit did not change it")
    return Miss(change, got, MissCause.RULE_SILENT, f"no rule fired; {sorted(change.alternations)}")


def measure_recall(pairs: list[ParallelPair], converter: Converter) -> RecallReport:
    """Convert the Narkamaŭka side and compare its changes with the attested ones."""
    tokens = hits = orth_hits = 0
    changes_seen: list[Change] = []
    misses: list[Miss] = []
    false_positives: list[tuple[str, str, str]] = []
    by_alternation: dict[str, list[int]] = {}
    used = 0

    for pair in pairs:
        n_tokens, changes = diff_pair(pair)
        if not n_tokens:
            continue
        used += 1
        tokens += n_tokens
        result = converter.convert(pair.narkamauka, Orthography.TARASKIEVICA)
        produced = {c.source.lower(): c.target for c in result.conversions}
        attested = {c.source.lower() for c in changes}

        for change in changes:
            changes_seen.append(change)
            got = produced.get(change.source.lower(), change.source)
            correct = got.lower() == change.expected.lower()
            hits += correct
            if change.orthographic:
                orth_hits += correct
                for code in change.alternations or {"other"}:
                    bucket = by_alternation.setdefault(code, [0, 0])
                    bucket[0] += correct
                    bucket[1] += 1
            if not correct:
                misses.append(classify(change, got, converter))

        # A word the two wikis spell identically needs no change, so a converter that
        # changes it anyway is wrong on this corpus. Same evidence, opposite direction.
        for conversion in result.conversions:
            if conversion.changed and conversion.source.lower() not in attested:
                false_positives.append(
                    (conversion.source, conversion.target, str(conversion.rule_id))
                )

    orthographic = [c for c in changes_seen if c.orthographic]
    return RecallReport(
        pairs=used,
        tokens=tokens,
        changes=len(changes_seen),
        orthographic_changes=len(orthographic),
        hits=hits,
        orthographic_hits=orth_hits,
        misses=misses,
        false_positives=false_positives,
        by_alternation={k: (v[0], v[1]) for k, v in sorted(by_alternation.items())},
    )


def write_misses(report: RecallReport, path: Path) -> None:
    """Every miss, grouped by cause — the work queue this whole harness exists to produce."""
    order = list(MissCause)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            f"# {len(report.misses)} miss(es) of {report.changes} attested changes "
            f"across {report.pairs} aligned sentence pairs\n"
            "# cause\tsource\texpected\tgot\talternations\tdetail\tsentence\n"
        )
        for cause in order:
            for miss in (m for m in report.misses if m.cause is cause):
                alternations = ",".join(sorted(miss.change.alternations)) or "-"
                fh.write(
                    f"{cause.value}\t{miss.change.source}\t{miss.change.expected}\t{miss.got}\t"
                    f"{alternations}\t{miss.detail}\t{miss.change.sentence}\n"
                )
