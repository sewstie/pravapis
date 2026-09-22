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
from pravapis.metrics import FP_DIRECTIONS, read_known_fps
from pravapis.pipeline import Converter
from pravapis.recall import measure_recall, measure_unresolved_flag, read_parallel
from pravapis.types import Orthography
from tests.conftest import DATA_DIR

BASELINE = DATA_DIR / "eval" / BASELINE_NAME
KNOWN_FPS = DATA_DIR / "eval" / "known_fps.tsv"


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
        flag = measure_unresolved_flag(pairs, converter, direction)
        measured[f"dev_{tag}_unresolved_flag_precision"] = flag.flag_precision
        measured[f"dev_{tag}_unresolved_flag_rate"] = flag.flag_rate

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


def test_every_dev_false_positive_is_listed(converter: Converter) -> None:
    """Each dev false positive is named in `data/eval/known_fps.tsv`, or the build fails.

    This is the half of the ratchet an aggregate cannot do. `precision` is a ratio, so a
    batch that fixes four false positives and introduces four others leaves it exactly
    where it was, and `test_dev_metrics_have_not_regressed` passes on a change that broke
    four words. Naming every one of them makes that batch fail on the four it broke,
    whatever the percentage does.

    Listing a form is not the same as accepting a defect. The cause column says which it
    is, and two of the rows here are real defects with a place to fix them — they are
    listed so the gate keeps working in the meantime, not to bless them.
    """
    pairs = read_parallel(_corpus(), "dev")
    known = {row.key for row in read_known_fps(KNOWN_FPS)}
    unlisted: list[str] = []
    for tag, direction in FP_DIRECTIONS.items():
        report = measure_recall(pairs, converter, "dev", direction)
        for source, target, rule in report.false_positives:
            if (tag, source.lower()) in known:
                continue
            entry = f"{tag}\t{source.lower()}\t{target.lower()}\t{rule or 'lexicon'}"
            if entry not in unlisted:
                unlisted.append(entry)

    assert unlisted == [], (
        f"{len(unlisted)} dev false positive(s) are not in data/eval/known_fps.tsv:\n  "
        + "\n  ".join(unlisted)
        + "\n\nThe converter changed a word both wikis spelled the same way. Read the "
        "sentence before listing it: if Збор 2005 licenses the change the corpus is "
        "simply not normalised (`reference_deviates`), but if it does not, the rule or "
        "the lexicon entry is what needs fixing. Then:\n"
        "  python scripts/build_known_fps.py   # adds the rows; you assign the cause"
    )
