"""The ratchet: dev metrics may rise, and the build fails when they fall.

`tests/test_negative_set.py` catches the specific words a bad stem breaks. This catches
the shape of the damage — a batch that moves recall two points up and precision four
points down is a batch that found native vocabulary, and no list of individual words has
to name the casualties for the build to say so.

The floor is `data/eval/baseline.json`, written by `scripts/update_baseline.py`, which
refuses to record a metric that fell unless someone passes a reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pravapis.baseline import BASELINE_NAME, TOLERANCE, compare, fingerprint, read_baseline
from pravapis.config import Config
from pravapis.pipeline import Converter
from pravapis.recall import measure_recall, read_parallel
from pravapis.types import Orthography
from tests.conftest import DATA_DIR

BASELINE = DATA_DIR / "eval" / BASELINE_NAME


@pytest.fixture(scope="module")
def baseline() -> dict[str, object]:
    if not BASELINE.is_file():
        pytest.skip(f"no {BASELINE_NAME}; run scripts/update_baseline.py")
    return read_baseline(BASELINE)


def _corpus() -> Path:
    path: Path = Config.default().lexicon.parent / "corpora" / "parallel.tsv"
    return path


def test_baseline_matches_the_corpus_it_was_taken_on(baseline: dict[str, object]) -> None:
    """A figure from a different corpus is not a floor, it is a different measurement.

    Every metric here is a ratio over a particular set of sentence pairs. Append four
    hundred and they all move for reasons that have nothing to do with the converter, so
    comparing across that line is noise with a pass/fail attached. It also closes the
    obvious way out: growing the corpus until a failing number comes back would
    otherwise be silent.
    """
    recorded = baseline["corpus"]
    assert isinstance(recorded, dict)
    current = fingerprint(_corpus())
    assert recorded["fingerprint"] == current, (
        f"the corpus changed ({recorded['fingerprint']} -> {current}), so the recorded "
        "metrics describe different sentences. Re-measure and re-baseline deliberately:\n"
        "  python scripts/update_baseline.py --milestone"
    )


def test_dev_metrics_have_not_regressed(converter: Converter, baseline: dict[str, object]) -> None:
    recorded = baseline["metrics"]
    assert isinstance(recorded, dict)
    pairs = read_parallel(_corpus(), "dev")
    measured: dict[str, float] = {}
    for direction, tag in (
        (Orthography.TARASKIEVICA, "n2t"),
        (Orthography.NARKAMAUKA, "t2n"),
    ):
        report = measure_recall(pairs, converter, "dev", direction)
        measured[f"dev_{tag}_recall"] = report.recall
        measured[f"dev_{tag}_precision"] = report.precision

    fell = [m for m in compare({k: float(v) for k, v in recorded.items()}, measured) if m.regressed]
    assert fell == [], (
        "dev metrics fell below the recorded baseline:\n  "
        + "\n  ".join(str(m) for m in fell)
        + f"\n(tolerance {TOLERANCE:.1%}.) A stem batch that raises recall while dropping "
        "precision has found native vocabulary — check data/eval/negative.tsv and the "
        "blast radius of what you just accepted. If the drop is genuinely correct:\n"
        '  python scripts/update_baseline.py --allow-regression "why"'
    )


def test_the_frozen_split_is_not_read_on_every_run(baseline: dict[str, object]) -> None:
    """Recorded at milestones, never asserted here.

    A test split read on every push is not frozen; it is a dev split with a slower
    feedback loop, and the number it finally reports means nothing. This test exists to
    state that on purpose, so nobody 'fixes' the omission later.
    """
    metrics = baseline["metrics"]
    assert isinstance(metrics, dict)
    assert "dev_n2t_recall" in metrics
