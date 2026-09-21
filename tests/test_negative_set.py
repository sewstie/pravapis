"""The precision gate: words the converter must leave alone, and the dev-split ratio.

Recall cannot see the error these catch. A stem that quietly starts matching native
vocabulary loses no recall at all — it only changes words nobody asked it to, and the
recall number goes *up* while the converter gets worse. `клас-` is right for кляса and
wrong for класці; longest match saves it only because a native `класц` guard exists.
These two tests are what make forgetting the guard fail the build rather than ship.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from pravapis.config import Config
from pravapis.metrics import read_negative_set
from pravapis.pipeline import Converter
from pravapis.recall import measure_recall, read_parallel
from pravapis.types import Orthography
from tests.conftest import DATA_DIR

N2T = Orthography.TARASKIEVICA

#: A REGRESSION FLOOR, not a quality claim, and deliberately not 99%.
#:
#: Measured dev precision is 95.3% [94.0, 96.3], and almost none of the shortfall is the
#: converter's. The errors it counts are words like `Салідарнасць → Салідарнасьць`,
#: `вобласці → вобласьці`, `не → ня` — §29 and §3, cited and unit-tested — where the
#: be-tarask article simply had not been converted. be-tarask is community-written and
#: not uniformly Taraškievica, so an unconverted word there is indistinguishable from a
#: converter error by this measurement. Gating at 99% would fail on the corpus's prose
#: habits and teach everyone to ignore the gate.
#:
#: So this catches the large drop a bad lexicon batch causes — the candidates leak that
#: prompted this file took it to 79.7% — and the *exact* gate is the negative set below,
#: which drops contested forms and therefore has no such noise in it at all.
MIN_DEV_PRECISION = 0.93


@pytest.fixture(scope="module")
def negative_set() -> list[tuple[str, int]]:
    return read_negative_set(DATA_DIR / "eval" / "negative.tsv")


def test_the_negative_set_is_not_empty(negative_set: list[tuple[str, int]]) -> None:
    assert negative_set, "run scripts/build_negative_set.py"


def test_every_attestation_count_meets_the_threshold(
    negative_set: list[tuple[str, int]],
) -> None:
    """One agreement can be one author's oversight; two is the documented minimum."""
    assert [form for form, n in negative_set if n < 2] == []


def test_converter_changes_nothing_in_the_negative_set(
    converter: Converter, negative_set: list[tuple[str, int]]
) -> None:
    """Both wikis wrote these identically. Nothing is due, so nothing may change."""
    changed = [
        (form, converter.convert(form, N2T).text)
        for form, _ in negative_set
        if converter.convert(form, N2T).text.lower() != form
    ]
    assert changed == [], (
        f"{len(changed)} word(s) both wikis spell alike were changed anyway: "
        + ", ".join(f"{s}→{t}" for s, t in changed[:10])
        + ". A new stem is probably catching native vocabulary — add the native guard "
        "to data/lexicon/stems/stems.tsv. If the change is genuinely right, delete the "
        "row and say why in the commit."
    )


def test_dev_precision_does_not_regress(converter: Converter) -> None:
    """Of the changes the converter makes on dev, at least 99% must be attested.

    The negative set catches a stem that fires on a word nobody writes differently.
    This catches the other half: a stem that fires on the right word and produces the
    wrong form. Dev rather than test, so the frozen split stays frozen.
    """
    corpus = Config.default().lexicon.parent / "corpora" / "parallel.tsv"
    pairs = read_parallel(corpus, "dev")
    if len(pairs) < 20:
        pytest.skip(f"dev split has {len(pairs)} pair(s); too few to gate on")
    report = measure_recall(pairs, converter, "dev")
    assert report.precision >= MIN_DEV_PRECISION, (
        f"dev precision {report.precision:.1%} is below {MIN_DEV_PRECISION:.0%}: "
        f"{len(report.false_positives)} change(s) where none was due, "
        f"{report.wrong_changes} wrong where one was. "
        "Run `pravapis eval --recall --split dev` to see them."
    )


# --- rebuilding must not launder a regression --------------------------------------
def _builder() -> Any:
    path = Path(__file__).resolve().parent.parent / "scripts" / "build_negative_set.py"
    spec = importlib.util.spec_from_file_location("build_negative_set", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rebuilding_keeps_a_pinned_row_the_converter_now_changes(tmp_path: Path) -> None:
    """The whole point of the file is to fail when one of its rows starts changing.

    If a rebuild dropped such a row, the sequence "add bad stem, rebuild, commit" would
    turn a caught regression into a green build — and the file would be a record of what
    the converter happens to do rather than of what it must do.
    """
    corpus = tmp_path / "parallel.tsv"
    corpus.write_text(
        "# narkamauka<TAB>taraskievica<TAB>title_be<TAB>revid_be"
        "<TAB>title_tarask<TAB>revid_tarask<TAB>similarity<TAB>split\n"
        "кот сеў на дыван\tкот сеў на дыван\tA\t1\tA\t2\t1.0\ttrain\n"
        "кот сеў на дыван\tкот сеў на дыван\tA\t1\tA\t2\t1.0\ttrain\n",
        encoding="utf-8",
    )
    out = tmp_path / "negative.tsv"
    # A word the converter certainly changes, pinned by hand as a stand-in for one that
    # regressed after the file was written.
    out.write_text("# form\tattestations\tnote\nснег\t9\t\n", encoding="utf-8")

    assert _builder().main(["--corpus", str(corpus), "--out", str(out)]) == 0

    forms = [form for form, _ in read_negative_set(out)]
    assert "снег" in forms, "a pinned row was dropped because the converter changes it"
