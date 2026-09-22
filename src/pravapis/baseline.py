"""The ratchet: numbers that are allowed to go up, and a build that fails when they go down.

A review batch adds stems. Stems are the one change that can improve the headline and
break the converter at the same time — a stem that catches native vocabulary raises
recall on the words it was meant for while quietly changing words nobody asked about.
The negative set catches the specific words it breaks; this catches the shape of the
damage, on every metric at once, without anybody having to remember what last week's
number was.

## Why a stored file rather than a threshold in a test

A constant in a test is a number somebody typed, and it drifts from the measurement it
was meant to track the first time anyone is in a hurry. A recorded baseline is the
measurement, with the date it was taken and the corpus it was taken on, and raising it
is a visible line in a diff.

## Why the corpus is fingerprinted

Recall is a ratio over a particular corpus. Append four hundred sentence pairs and every
figure moves for reasons that have nothing to do with the converter — so a baseline from
the old corpus compared against the new one is not a regression test, it is noise with a
pass/fail attached. The fingerprint makes that case say "re-baseline", which is a
decision someone takes deliberately, rather than a red build somebody learns to ignore.

It is also the honest way round: without it, the way to make a failing ratchet pass is
to grow the corpus until the number comes back, and nothing would report that.

## What is watched, and what is not

`dev` is watched on every run. `test` is recorded when someone updates the baseline at a
milestone and is **not** asserted on every run: a frozen split read on every push is not
frozen, it is just a slower dev split.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final

#: How far a metric may fall before the build fails. Not zero: the metrics are ratios of
#: integers, so a single sentence pair re-tokenising differently after an unrelated
#: change can move the last decimal. Anything a bad stem batch does is far larger — the
#: candidates leak that motivated this file moved precision by sixteen points.
TOLERANCE: Final[float] = 0.002

BASELINE_NAME: Final[str] = "baseline.json"


#: Metrics named with this suffix are ratios where *lower* is the improvement — a
#: ceiling, not a floor (``dev_n2t_unresolved_flag_rate`` and friends). Everything
#: else that ends in ``_recall``/``_precision`` ratchets upward as usual.
LOWER_IS_BETTER_SUFFIXES: Final[tuple[str, ...]] = ("_rate",)


def format_value(name: str, value: float) -> str:
    """Ratios as percentages, counts as counts.

    ``negative_set_forms`` is 3,213 words, not 321,300%.
    """
    if name.endswith(("_recall", "_precision", *LOWER_IS_BETTER_SUFFIXES)):
        return f"{value:.2%}"
    return f"{value:,.0f}"


@dataclass(frozen=True, slots=True)
class Metric:
    name: str
    recorded: float
    measured: float

    @property
    def delta(self) -> float:
        return self.measured - self.recorded

    @property
    def regressed(self) -> bool:
        """A count may not shrink either: the negative set losing rows is the laundering
        move `scripts/build_negative_set.py` already refuses, caught a second time here.

        A ``_rate`` metric is the one ratio that ratchets the other way: it is a
        ceiling (``dev_n2t_unresolved_flag_rate`` should stay low), so *rising* past
        tolerance is the regression, not falling.
        """
        if self.name.endswith(LOWER_IS_BETTER_SUFFIXES):
            return self.delta > TOLERANCE
        if self.name.endswith(("_recall", "_precision")):
            return self.delta < -TOLERANCE
        return self.measured < self.recorded

    def __str__(self) -> str:
        measured = format_value(self.name, self.measured)
        recorded = format_value(self.name, self.recorded)
        if self.name.endswith(("_recall", "_precision", *LOWER_IS_BETTER_SUFFIXES)):
            return f"{self.name}: {measured} vs baseline {recorded} ({self.delta:+.2%})"
        return f"{self.name}: {measured} vs baseline {recorded} ({self.delta:+,.0f})"


def fingerprint(path: Path) -> str:
    """A hash of the corpus's data rows, ignoring comments.

    Comments carry counts and prose that get rewritten by unrelated edits; the rows are
    what the measurement is over. Sixteen hex digits is plenty to notice a change and
    short enough to read in a diff.
    """
    digest = hashlib.sha256()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            digest.update(line.encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest()[:16]


def read_baseline(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def write_baseline(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compare(recorded: dict[str, float], measured: dict[str, float]) -> list[Metric]:
    """Every metric present in both, as ``Metric`` objects, in recorded order."""
    return [
        Metric(name, float(value), float(measured[name]))
        for name, value in recorded.items()
        if name in measured
    ]


def raised(recorded: dict[str, float], measured: dict[str, float]) -> dict[str, float]:
    """The new record: each metric's better value. This is the ratchet.

    A metric that got worse keeps its recorded value, so the file never learns a worse
    number by accident. Making one worse deliberately is possible — sometimes a rule is
    corrected and a figure that was flattering it moves honestly — but it takes
    `--allow-regression` and a reason, and the reason is written into the file next to
    the number.

    "Better" means higher for everything except a ``_rate`` ceiling metric, where it
    means lower — see :data:`LOWER_IS_BETTER_SUFFIXES`.
    """
    out = dict(recorded)
    for name, value in measured.items():
        previous = float(recorded.get(name, value))
        better = min if name.endswith(LOWER_IS_BETTER_SUFFIXES) else max
        out[name] = better(float(value), previous)
    return out


def today() -> str:
    return date.today().isoformat()
