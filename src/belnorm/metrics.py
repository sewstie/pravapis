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
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from belnorm.normalize import sanitize
from belnorm.pipeline import Converter
from belnorm.rules.engine import RuleEngine
from belnorm.tokenize import tokenize
from belnorm.types import Conversion, Method, Orthography, TokenKind


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
    round_trip: float | None = None
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


def round_trip_consistency(texts: Sequence[str], converter: Converter) -> float:
    """Share of texts for which N→T→N reproduces the (sanitised) original."""
    if not texts:
        return 0.0
    ok = 0
    for text in texts:
        original = sanitize(text)
        there = converter.convert(original, Orthography.TARASKIEVICA).text
        back = converter.convert(there, Orthography.NARKAMAUKA).text
        ok += back == original
    return ok / len(texts)


@dataclass(frozen=True, slots=True)
class RoundTripFailure:
    """One word for which N→T→N did not return the original."""

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
    texts: Iterable[str], converter: Converter
) -> tuple[int, list[RoundTripFailure]]:
    """Word-level N→T→N check. Returns (words checked, failures)."""
    n_words = 0
    failures: list[RoundTripFailure] = []
    for text in texts:
        original = sanitize(text)
        there = converter.convert(original, Orthography.TARASKIEVICA)
        back = converter.convert(there.text, Orthography.NARKAMAUKA)
        if len(there.conversions) != len(back.conversions):
            continue  # tokenisation changed; counted by the sentence-level metric
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


def read_gold(path: Path) -> list[tuple[str, str]]:
    """``narkamauka<TAB>taraskievica[<TAB>extra columns…]`` lines.

    Blank lines and ``#`` comments are skipped; columns after the second
    (provenance, review status) are ignored.
    """
    pairs: list[tuple[str, str]] = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            a, b, *_ = [*line.split("\t"), ""]
            pairs.append((sanitize(a.strip()), sanitize(b.strip())))
    return pairs


def _words(text: str) -> list[str]:
    return [t.text for t in tokenize(text) if t.kind is TokenKind.WORD]


def evaluate(
    converter: Converter,
    pairs: Iterable[tuple[str, str]],
    direction: Orthography = Orthography.TARASKIEVICA,
    *,
    error_limit: int = 50,
    round_trip: bool = True,
) -> EvalReport:
    """Word-align each gold pair and score the converter on it."""
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
    if round_trip:
        n_texts = [n for n, _ in materialised]
        rt = round_trip_consistency(n_texts, converter)
    return EvalReport(
        direction=direction,
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
        per_rule=per_rule,
        changed_words=n_changed,
        changed_correct=changed_correct,
        false_positives=false_positives,
        baseline_accuracy=baseline_correct / n_words if n_words else 0.0,
        baseline_sentence_accuracy=(
            baseline_sentence_ok / len(materialised) if materialised else 0.0
        ),
    )
