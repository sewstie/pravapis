"""Evaluation.

Most Belarusian words are spelled identically in both orthographies, so raw
word accuracy is dominated by words the converter only has to leave alone.
Every number here is therefore reported against the **do-nothing baseline**
(return the input unchanged), and accuracy is split in two:

* **change accuracy** — of the words whose gold form differs from the source,
  the share converted exactly right. This is the real number.
* **false-positive rate** — of the words whose gold form equals the source,
  the share the converter changed anyway. Catches over-applied rules.

Also: coverage split by method, round-trip consistency, throughput.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final

import regex

from pravapis.normalize import sanitize
from pravapis.pipeline import Converter
from pravapis.rules.engine import RuleEngine
from pravapis.tokenize import tokenize
from pravapis.types import Conversion, Method, Orthography, TokenKind


@dataclass(frozen=True, slots=True)
class MethodStats:
    count: int
    share: float  # of all word tokens
    correct: int | None = None  # only known when gold is available

    @property
    def accuracy(self) -> float | None:
        if self.correct is None or self.count == 0:
            return None
        return self.correct / self.count


@dataclass(frozen=True, slots=True)
class PRF:
    precision: float
    recall: float
    f1: float
    support: int  # times the rule fired


@dataclass(frozen=True, slots=True)
class ErrorCase:
    index: int
    source: str
    predicted: str
    expected: str
    method: Method | None = None
    rule_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvalReport:
    direction: Orthography
    pairs: int
    words: int
    accuracy: float
    breakdown: dict[Method, MethodStats]
    errors: list[ErrorCase]
    seconds: float
    bytes_processed: int
    misaligned: int = 0
    sentence_accuracy: float = 0.0
    round_trip: float | None = None  # sentence level
    word_round_trip: float | None = None
    per_rule: dict[str, PRF] = field(default_factory=dict)
    #: aligned words whose gold form differs from the source
    changed_words: int = 0
    #: of those, converted exactly right
    changed_correct: int = 0
    #: of the unchanged words, how many the converter altered anyway
    false_positives: int = 0
    #: accuracy of returning every word unchanged
    baseline_accuracy: float = 0.0
    baseline_sentence_accuracy: float = 0.0
    #: orthography the gold sentences were authored in, from the file's `# origin:` header
    origin: Orthography | None = None

    @property
    def is_independent(self) -> bool:
        """True when the source side of this direction was written by a human.

        False means the source side was derived from the other one, so the figure is
        self-consistency rather than accuracy. None (no header) is treated as unknown
        and reported as such rather than assumed independent.
        """
        return self.origin is not None and self.origin is not self.direction

    @property
    def unchanged_words(self) -> int:
        return self.words - self.changed_words

    @property
    def change_accuracy(self) -> float:
        return self.changed_correct / self.changed_words if self.changed_words else 0.0

    @property
    def false_positive_rate(self) -> float:
        return self.false_positives / self.unchanged_words if self.unchanged_words else 0.0

    @property
    def error_reduction(self) -> float:
        """Share of the baseline's word errors the converter removed (can be negative)."""
        base_err = 1.0 - self.baseline_accuracy
        return (self.accuracy - self.baseline_accuracy) / base_err if base_err else 0.0

    @property
    def mb_per_second(self) -> float:
        return (self.bytes_processed / 1_000_000) / self.seconds if self.seconds else 0.0


def word_accuracy(pred: Sequence[str], gold: Sequence[str]) -> float:
    if len(pred) != len(gold):
        raise ValueError(f"length mismatch: {len(pred)} predictions vs {len(gold)} gold")
    if not gold:
        return 0.0
    return sum(p == g for p, g in zip(pred, gold, strict=True)) / len(gold)


def per_method_breakdown(results: Sequence[Conversion]) -> dict[Method, MethodStats]:
    total = len(results)
    counts = Counter(c.method for c in results)
    return {m: MethodStats(counts[m], counts[m] / total if total else 0.0) for m in Method}


def per_rule_precision_recall(
    traces: Sequence[tuple[str, Sequence[str], str]],
    gold: Sequence[str],
    engine: RuleEngine,
    direction: Orthography,
) -> dict[str, PRF]:
    """Per-rule precision/recall.

    ``traces`` are ``(source, fired_rule_ids, predicted)`` triples aligned with
    ``gold``. A rule's *precision* is the share of its firings that ended in a
    correct word. Its *recall* is TP / (TP + missed), where a *miss* is a pair
    the rule alone would have turned into the gold form but on which it did
    not fire.
    """
    if len(traces) != len(gold):
        raise ValueError("traces and gold must be aligned")
    tp: Counter[str] = Counter()
    fired: Counter[str] = Counter()
    missed: Counter[str] = Counter()
    rules = engine.rules_for(direction)
    for (source, fired_ids, predicted), expected in zip(traces, gold, strict=True):
        for rid in fired_ids:
            fired[rid] += 1
            if predicted == expected:
                tp[rid] += 1
        if source != expected:
            for rule in rules:
                if rule.id not in fired_ids and rule.transform(source) == expected:
                    missed[rule.id] += 1
    out: dict[str, PRF] = {}
    for rid in set(fired) | set(missed):
        p = tp[rid] / fired[rid] if fired[rid] else 0.0
        denominator = tp[rid] + missed[rid]
        r = tp[rid] / denominator if denominator else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
        out[rid] = PRF(p, r, f1, fired[rid])
    return out


def _other(o: Orthography) -> Orthography:
    return Orthography.NARKAMAUKA if o is Orthography.TARASKIEVICA else Orthography.TARASKIEVICA


def round_trip_consistency(
    texts: Sequence[str], converter: Converter, start: Orthography = Orthography.NARKAMAUKA
) -> float:
    """Share of texts (written in ``start``) that survive a there-and-back conversion unchanged."""
    if not texts:
        return 0.0
    ok = 0
    for text in texts:
        original = sanitize(text)
        there = converter.convert(original, _other(start)).text
        back = converter.convert(there, start).text
        ok += back == original
    return ok / len(texts)


@dataclass(frozen=True, slots=True)
class RoundTripFailure:
    """One word for which a there-and-back conversion did not return the original."""

    sentence: str
    source: str
    there: str
    back: str
    there_method: Method
    there_rule: str | None
    back_method: Method
    back_rule: str | None

    @property
    def group(self) -> str:
        """Which stage broke it: the N→T resolution, then the T→N one."""
        there = self.there_rule or self.there_method.value
        back = self.back_rule or self.back_method.value
        return f"{there} | {back}"


def round_trip_failures(
    texts: Iterable[str], converter: Converter, start: Orthography = Orthography.NARKAMAUKA
) -> tuple[int, list[RoundTripFailure]]:
    """Word-level round trip for texts written in ``start``. Returns (words checked, failures).

    If the word count changes on the way, every word of that sentence counts
    as a failure (grouped as ``tokenisation``) rather than being dropped.
    """
    n_words = 0
    failures: list[RoundTripFailure] = []
    for text in texts:
        original = sanitize(text)
        there = converter.convert(original, _other(start))
        back = converter.convert(there.text, start)
        if len(there.conversions) != len(back.conversions):
            n_words += len(there.conversions)
            failures.extend(
                RoundTripFailure(
                    original, t.source, t.target, "", t.method, "tokenisation", Method.UNKNOWN, None
                )
                for t in there.conversions
            )
            continue
        for t, b in zip(there.conversions, back.conversions, strict=True):
            n_words += 1
            if b.target != t.source:
                failures.append(
                    RoundTripFailure(
                        original,
                        t.source,
                        t.target,
                        b.target,
                        t.method,
                        t.rule_id,
                        b.method,
                        b.rule_id,
                    )
                )
    return n_words, failures


def read_regressions(path: Path | None = None) -> list[tuple[str, str]]:
    """Pinned round-trip regressions from ``data/eval/roundtrip_regressions.tsv``.

    Data rather than a list in a test file, so the same rows can be exported into the
    conformance corpus. A port that reimplements a rule which overreaches will
    reintroduce exactly these, and rediscovering them costs whatever it cost here.
    """
    from pravapis.config import find_data_dir

    target = path or find_data_dir() / "eval" / "roundtrip_regressions.tsv"
    rows: list[tuple[str, str]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((sanitize(parts[0].strip()), sanitize(parts[1].strip())))
    return rows


def read_negative_set(path: Path | None = None) -> list[tuple[str, int]]:
    """``(form, attestations)`` the converter must leave unchanged, N → T.

    Built by ``scripts/build_negative_set.py`` from the train split of the parallel
    corpus: words a Narkamaŭka writer and a Taraškievica writer independently spelled
    the same way. Recall cannot see the error these catch — a stem that quietly starts
    matching native vocabulary loses no recall at all, it just changes words nobody
    asked it to.
    """
    from pravapis.config import find_data_dir

    target = path or find_data_dir() / "eval" / "negative.tsv"
    rows: list[tuple[str, int]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("	")
        if len(parts) >= 2 and parts[1].strip().isdigit():
            rows.append((sanitize(parts[0].strip()), int(parts[1].strip())))
    return rows


def write_round_trip_failures(
    texts: Sequence[str],
    converter: Converter,
    path: Path,
    corpus_name: str = "corpus",
    start: Orthography = Orthography.NARKAMAUKA,
) -> tuple[int, list[RoundTripFailure], list[tuple[str, list[RoundTripFailure]]]]:
    """Round-trip ``texts`` and dump every word that did not come back, grouped by cause.

    Returns ``(words checked, failures, groups)``. Shared by ``pravapis eval
    --round-trip`` and ``scripts/mine_roundtrip.py`` so the file one writes and the rate
    the other prints can never describe different runs.
    """
    from collections import defaultdict

    n_words, failures = round_trip_failures(texts, converter, start)
    grouped: dict[str, list[RoundTripFailure]] = defaultdict(list)
    for failure in failures:
        grouped[failure.group].append(failure)
    groups = sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            f"# {len(failures)} failing words of {n_words} "
            f"({1 - len(failures) / n_words if n_words else 0:.2%} word round trip) "
            f"from {corpus_name}\n"
        )
        fh.write("# group (N→T stage | T→N stage)\tsource\ttaraskievica\tback\tsentence\n")
        for _, items in groups:
            for f in items:
                fh.write(f"{f.group}\t{f.source}\t{f.there}\t{f.back}\t{f.sentence}\n")
    return n_words, failures, groups


def error_report(
    pred: Sequence[str],
    gold: Sequence[str],
    *,
    limit: int = 50,
    sources: Sequence[str] | None = None,
) -> list[ErrorCase]:
    errors: list[ErrorCase] = []
    for i, (p, g) in enumerate(zip(pred, gold, strict=True)):
        if p != g:
            errors.append(ErrorCase(i, sources[i] if sources else "", p, g))
            if len(errors) >= limit:
                break
    return errors


HAND_WRITTEN = "hand_written"
CONVERTER_CHECKED = "converter_checked"
#: corrected against Збор правілаў 2005 after the converter disagreed: scored, not --trusted
CODIFICATION_CHECKED = "codification_checked"
UNCERTAIN = "uncertain"
#: a machine-written proposal awaiting human review. Never scored — scoring a converter
#: proposal against the converter would return 100% by construction. Promote a row to
#: hand_written once a human has read and corrected it.
PROPOSED = "proposed"
PROVENANCES = frozenset(
    {HAND_WRITTEN, CONVERTER_CHECKED, CODIFICATION_CHECKED, UNCERTAIN, PROPOSED}
)
#: provenances excluded from every score
UNSCORED: Final[frozenset[str]] = frozenset({UNCERTAIN, PROPOSED})


@dataclass(frozen=True, slots=True)
class GoldRow:
    narkamauka: str
    taraskievica: str
    source: str = ""
    provenance: str = ""  # hand_written | converter_checked | uncertain | "" (legacy 2-column)


_ORIGIN_RE: Final[regex.Pattern[str]] = regex.compile(r"^#\s*origin:\s*(\w+)", regex.I)


def read_gold_origin(path: Path) -> Orthography | None:
    """The orthography a gold file's sentences were *authored* in, from its header.

    ``# origin: narkamauka`` means a human wrote the Narkamaŭka side and the
    Taraškievica side was derived from it. Scoring the derived direction then measures
    whether the converter can undo a transformation produced by the same reading of the
    norm it implements — self-consistency, not accuracy. Reporting depends on knowing
    which is which, so the file says so itself rather than leaving it to a README.
    """
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            if not raw.lstrip().startswith("#"):
                break
            m = _ORIGIN_RE.match(raw.strip())
            if m:
                try:
                    return Orthography(m.group(1).lower())
                except ValueError:
                    return None
    return None


def read_gold_rows(path: Path) -> list[GoldRow]:
    """``narkamauka<TAB>taraskievica[<TAB>source<TAB>provenance]`` lines; ``#`` comments skipped."""
    rows: list[GoldRow] = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            a, b, source, provenance, *_ = [*line.split("\t"), "", "", ""]
            rows.append(
                GoldRow(
                    sanitize(a.strip()), sanitize(b.strip()), source.strip(), provenance.strip()
                )
            )
    return rows


def read_gold(path: Path, *, trusted_only: bool = False) -> list[tuple[str, str]]:
    """Scorable gold pairs: ``uncertain`` rows are always excluded.

    ``trusted_only`` keeps just the ``hand_written`` rows — the subset never
    adjusted after seeing converter output.
    """
    return [
        (r.narkamauka, r.taraskievica)
        for r in read_gold_rows(path)
        if r.provenance not in UNSCORED and (not trusted_only or r.provenance == HAND_WRITTEN)
    ]


def _words(text: str) -> list[str]:
    return [t.text for t in tokenize(text) if t.kind is TokenKind.WORD]


def evaluate(
    converter: Converter,
    pairs: Iterable[tuple[str, str]],
    direction: Orthography = Orthography.TARASKIEVICA,
    *,
    error_limit: int = 50,
    round_trip: bool = True,
    origin: Orthography | None = None,
) -> EvalReport:
    """Word-align each gold pair and score the converter on it.

    ``origin`` is the orthography the gold sentences were authored in (see
    :func:`read_gold_origin`). It does not change any number — it labels them, so a
    derived direction cannot be read as independent evidence.
    """
    materialised = list(pairs)
    sources = [n if direction is Orthography.TARASKIEVICA else t for n, t in materialised]
    expected = [t if direction is Orthography.TARASKIEVICA else n for n, t in materialised]

    start = time.perf_counter()
    results = [converter.convert(s, direction) for s in sources]
    seconds = time.perf_counter() - start

    conversions: list[Conversion] = []
    correct_by_method: Counter[Method] = Counter()
    errors: list[ErrorCase] = []
    misaligned = 0
    sentence_ok = 0
    baseline_sentence_ok = 0
    n_words = 0
    n_correct = 0
    n_changed = 0
    changed_correct = 0
    baseline_correct = 0
    false_positives = 0
    for i, (res, src, exp) in enumerate(zip(results, sources, expected, strict=True)):
        sentence_ok += res.text == exp
        baseline_sentence_ok += src == exp
        gold_words = _words(exp)
        if len(gold_words) != len(res.conversions):
            misaligned += 1
            continue
        for conv, gold_word in zip(res.conversions, gold_words, strict=True):
            conversions.append(conv)
            n_words += 1
            ok = conv.target == gold_word
            if conv.source == gold_word:
                baseline_correct += 1
                false_positives += not ok
            else:
                n_changed += 1
                changed_correct += ok
            if ok:
                n_correct += 1
                correct_by_method[conv.method] += 1
            elif len(errors) < error_limit:
                errors.append(
                    ErrorCase(i, conv.source, conv.target, gold_word, conv.method, conv.rule_id)
                )
    counts = Counter(c.method for c in conversions)
    breakdown = {
        m: MethodStats(counts[m], counts[m] / n_words if n_words else 0.0, correct_by_method[m])
        for m in Method
    }
    traces = [
        (c.source.lower(), (c.rule_id or "").split("+") if c.rule_id else [], c.target.lower())
        for c in conversions
    ]
    gold_lower = [
        g.lower()
        for res, exp in zip(results, expected, strict=True)
        if len(_words(exp)) == len(res.conversions)
        for g in _words(exp)
    ]
    per_rule = per_rule_precision_recall(traces, gold_lower, converter.engine, direction)
    rt = None
    word_rt = None
    if round_trip:
        # Start from the side this direction reads: →T scores N→T→N, →N scores T→N→T.
        rt_start = _other(direction)
        rt = round_trip_consistency(sources, converter, rt_start)
        rt_words, rt_failures = round_trip_failures(sources, converter, rt_start)
        word_rt = 1 - len(rt_failures) / rt_words if rt_words else 0.0
    return EvalReport(
        direction=direction,
        origin=origin,
        pairs=len(materialised),
        words=n_words,
        accuracy=n_correct / n_words if n_words else 0.0,
        breakdown=breakdown,
        errors=errors,
        seconds=seconds,
        bytes_processed=sum(len(s.encode("utf-8")) for s in sources),
        misaligned=misaligned,
        sentence_accuracy=sentence_ok / len(materialised) if materialised else 0.0,
        round_trip=rt,
        word_round_trip=word_rt,
        per_rule=per_rule,
        changed_words=n_changed,
        changed_correct=changed_correct,
        false_positives=false_positives,
        baseline_accuracy=baseline_correct / n_words if n_words else 0.0,
        baseline_sentence_accuracy=(
            baseline_sentence_ok / len(materialised) if materialised else 0.0
        ),
    )


# --- independent evaluation on genuine Taraškievica ---------------------------------------
# data/eval/gold.tsv is Narkamaŭka in origin: its Taraškievica side was written by applying
# the 2005 norm to Narkamaŭka text. Scoring T → N on it asks whether the converter can undo
# a transformation derived from the same reading of the norm it implements — self-consistency,
# not accuracy. The audit below scores the other direction against text nobody derived.

OK = "ok"
WRONG = "wrong"
UNSURE = "unsure"
#: an empty verdict means "not yet reviewed"; it is counted, never scored
VERDICTS: Final[frozenset[str]] = frozenset({OK, WRONG, UNSURE, ""})


@dataclass(frozen=True, slots=True)
class CorpusRow:
    sentence: str
    article: str = ""
    revid: str = ""


def read_corpus(path: Path) -> list[CorpusRow]:
    """``sentence<TAB>article<TAB>revid`` lines; ``#`` comments skipped."""
    rows: list[CorpusRow] = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            sentence, article, revid, *_ = [*line.split("\t"), "", ""]
            rows.append(CorpusRow(sanitize(sentence.strip()), article.strip(), revid.strip()))
    return rows


@dataclass(frozen=True, slots=True)
class AuditRow:
    """One distinct change the converter makes, with however often it makes it."""

    source: str
    target: str
    rule: str
    count: int
    verdict: str = ""
    note: str = ""
    example: str = ""

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.source, self.target, self.rule)


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Precision over *reviewed* changes, weighted by how often each occurs.

    Weighting by frequency is what makes the review affordable: thousands of changed
    tokens collapse to a few hundred distinct changes, and the most frequent ones carry
    most of the mass. ``unreviewed`` is reported next to the number so a half-finished
    audit reads as partial rather than flattering.
    """

    distinct: int
    tokens: int
    ok_tokens: int = 0
    wrong_tokens: int = 0
    unsure_tokens: int = 0
    unreviewed_tokens: int = 0
    ok_rows: int = 0
    wrong_rows: int = 0
    unsure_rows: int = 0
    unreviewed_rows: int = 0

    @property
    def scored_tokens(self) -> int:
        return self.ok_tokens + self.wrong_tokens

    @property
    def precision(self) -> float | None:
        """None when nothing has been reviewed — not 0.0, and not 1.0."""
        return self.ok_tokens / self.scored_tokens if self.scored_tokens else None

    @property
    def reviewed_share(self) -> float:
        return (self.tokens - self.unreviewed_tokens) / self.tokens if self.tokens else 0.0


def audit_changes(
    converter: Converter,
    sentences: Iterable[str],
    direction: Orthography,
) -> list[AuditRow]:
    """Every distinct word the converter changes, counted, most frequent first.

    One row per (source, target, rule): the unit a human can actually judge. Judging
    tokens would mean reading the same change hundreds of times.
    """
    counts: Counter[tuple[str, str, str]] = Counter()
    examples: dict[tuple[str, str, str], str] = {}
    for sentence in sentences:
        result = converter.convert(sentence, direction)
        for conv in result.conversions:
            if conv.target == conv.source:
                continue
            key = (conv.source, conv.target, conv.rule_id or conv.method.value)
            counts[key] += 1
            examples.setdefault(key, sentence)
    return [
        AuditRow(source=s, target=t, rule=r, count=n, example=examples[(s, t, r)])
        for (s, t, r), n in counts.most_common()
    ]


def read_audit(path: Path) -> dict[tuple[str, str, str], AuditRow]:
    """Existing verdicts, keyed so a re-run can preserve them."""
    if not path.is_file():
        return {}
    rows: dict[tuple[str, str, str], AuditRow] = {}
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            source, target, rule, count, verdict, note, example, *_ = [
                *line.split("\t"),
                "",
                "",
                "",
                "",
            ]
            row = AuditRow(
                source=source.strip(),
                target=target.strip(),
                rule=rule.strip(),
                count=int(count) if count.strip().isdigit() else 0,
                verdict=verdict.strip(),
                note=note.strip(),
                example=example.strip(),
            )
            rows[row.key] = row
    return rows


def merge_audit(
    fresh: Sequence[AuditRow], existing: Mapping[tuple[str, str, str], AuditRow]
) -> list[AuditRow]:
    """Fresh counts, existing verdicts. A change that no longer occurs is dropped.

    Dropping stale rows is deliberate: a verdict on a change the converter no longer
    makes would keep counting towards a precision figure it no longer describes.
    """
    merged: list[AuditRow] = []
    for row in fresh:
        old = existing.get(row.key)
        merged.append(replace(row, verdict=old.verdict, note=old.note) if old is not None else row)
    return merged


AUDIT_HEADER: Final[str] = (
    "# source<TAB>target<TAB>rule<TAB>count<TAB>verdict<TAB>note<TAB>example\n"
    "# verdict: ok | wrong | unsure | (blank = not yet reviewed)\n"
    "# One row per distinct change, most frequent first. Fill in `verdict`; re-running\n"
    "# `pravapis audit` keeps what you wrote and re-counts against the current converter.\n"
)


def write_audit(rows: Sequence[AuditRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "\t".join((r.source, r.target, r.rule, str(r.count), r.verdict, r.note, r.example))
        for r in rows
    ]
    path.write_text(AUDIT_HEADER + "\n".join(lines) + "\n", encoding="utf-8")


def audit_precision(rows: Iterable[AuditRow]) -> AuditReport:
    materialised = list(rows)
    buckets: Counter[str] = Counter()
    row_buckets: Counter[str] = Counter()
    for r in materialised:
        buckets[r.verdict] += r.count
        row_buckets[r.verdict] += 1
    return AuditReport(
        distinct=len(materialised),
        tokens=sum(r.count for r in materialised),
        ok_tokens=buckets[OK],
        wrong_tokens=buckets[WRONG],
        unsure_tokens=buckets[UNSURE],
        unreviewed_tokens=buckets[""],
        ok_rows=row_buckets[OK],
        wrong_rows=row_buckets[WRONG],
        unsure_rows=row_buckets[UNSURE],
        unreviewed_rows=row_buckets[""],
    )


#: Why a change the corpus calls a false positive is there. The vocabulary is small on
#: purpose: each value names **where a fix would go**, the same way
#: :class:`pravapis.recall.MissCause` does for the other side of the ledger.
#:
#: ``reference_deviates``  the corpus side that should carry the target form does not.
#:                         Збор 2005 licenses the change; the wiki text is simply not
#:                         normalised. Nothing to fix in the converter.
#: ``proper_noun``         a name both wikis preserved as written — «Адраджэньне»,
#:                         Тацьцяна, Менск. A fix needs proper-noun detection, which
#:                         this converter does not have and does not pretend to.
#: ``rule_unsourced``      the rule that fired has no cited §. Whether the change is
#:                         right is an open question, logged in data/review/.
#: ``lexicon_overreach``   a lexicon entry substituted where the context does not
#:                         license it. A real defect with a row to edit.
#: ``rule_overreach``      the rule fires outside what its § licenses, and the output
#:                         is wrong in both orthographies. A real defect with a rule to
#:                         narrow — listed here so the gate stays honest until it is
#:                         fixed, never as a way of blessing it.
FP_CAUSES: Final[frozenset[str]] = frozenset(
    {
        "reference_deviates",
        "proper_noun",
        "rule_unsourced",
        "lexicon_overreach",
        "rule_overreach",
    }
)

#: ``n2t`` / ``t2n`` as written in ``data/eval/known_fps.tsv``.
FP_DIRECTIONS: Final[dict[str, Orthography]] = {
    "n2t": Orthography.TARASKIEVICA,
    "t2n": Orthography.NARKAMAUKA,
}


@dataclass(frozen=True, slots=True)
class KnownFalsePositive:
    """One word form the dev split says the converter should not have changed."""

    direction: str  # n2t | t2n
    source: str  # lowercased, as the corpus writes it
    target: str  # lowercased, what the converter produced
    rule: str  # rule id, or "lexicon" when no rule fired
    cause: str
    note: str = ""

    @property
    def key(self) -> tuple[str, str]:
        """What the gate matches on: the word form, per direction."""
        return (self.direction, self.source)


def read_known_fps(path: Path | None = None) -> list[KnownFalsePositive]:
    """The accepted dev false positives from ``data/eval/known_fps.tsv``.

    A file of word forms, not a rate. An aggregate precision floor cannot tell a batch
    that fixed four false positives and introduced four others from one that changed
    nothing, and that is the regression this list is here to catch: every dev false
    positive is named, so a *new* one fails the build whatever the percentage does.

    Rows are keyed on ``(direction, source)`` — the word form, as the spec for this
    gate says. ``target``, ``rule`` and ``cause`` are carried for the reader, not
    matched on: a rule change that alters what the converter produces for an
    already-accepted form is a different event from a form that was never accepted.
    """
    from pravapis.config import find_data_dir

    target = path or find_data_dir() / "eval" / "known_fps.tsv"
    rows: list[KnownFalsePositive] = []
    for number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            raise ValueError(f"{target}:{number}: expected 5 or 6 columns, got {len(parts)}")
        direction, source, produced, rule, cause = (p.strip() for p in parts[:5])
        if direction not in FP_DIRECTIONS:
            raise ValueError(
                f"{target}:{number}: direction {direction!r} is not one of {sorted(FP_DIRECTIONS)}"
            )
        if cause not in FP_CAUSES:
            raise ValueError(
                f"{target}:{number}: cause {cause!r} is not one of {sorted(FP_CAUSES)}"
            )
        rows.append(
            KnownFalsePositive(
                direction=direction,
                source=sanitize(source).lower(),
                target=sanitize(produced).lower(),
                rule=rule,
                cause=cause,
                note=parts[5].strip() if len(parts) > 5 else "",
            )
        )
    return rows
