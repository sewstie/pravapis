"""Independent T → N evaluation: origin headers, the precision audit, the tarask corpus.

data/eval/gold.tsv is Narkamaŭka in origin — its Taraškievica side was written from its
Narkamaŭka side — so scoring T → N on it measures self-consistency, not accuracy. These
tests guard the machinery that keeps those two things apart, and the corpus of genuine
Taraškievica that makes a real T → N figure possible.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from pravapis.metrics import (
    HAND_WRITTEN,
    OK,
    PROPOSED,
    PROVENANCES,
    UNSCORED,
    VERDICTS,
    WRONG,
    AuditRow,
    audit_changes,
    audit_precision,
    evaluate,
    merge_audit,
    read_audit,
    read_corpus,
    read_gold,
    read_gold_origin,
    read_gold_rows,
    write_audit,
)
from pravapis.pipeline import Converter
from pravapis.types import Orthography

ROOT = Path(__file__).resolve().parent.parent
TARASK = ROOT / "data" / "eval" / "tarask"
CORPUS = TARASK / "corpus.tsv"
GOLD_T2N = TARASK / "gold_t2n.tsv"
GOLD = ROOT / "data" / "eval" / "gold.tsv"

N2T = Orthography.TARASKIEVICA
T2N = Orthography.NARKAMAUKA


# --- origin headers -----------------------------------------------------------------------
def test_gold_declares_narkamauka_origin() -> None:
    assert read_gold_origin(GOLD) is Orthography.NARKAMAUKA


def test_independent_gold_declares_taraskievica_origin() -> None:
    assert read_gold_origin(GOLD_T2N) is Orthography.TARASKIEVICA


def test_origin_is_absent_when_unstated(tmp_path: Path) -> None:
    path = tmp_path / "g.tsv"
    path.write_text("# no header\nа\tа\ts\thand_written\n", encoding="utf-8")
    assert read_gold_origin(path) is None


def test_unknown_origin_is_none_not_a_crash(tmp_path: Path) -> None:
    path = tmp_path / "g.tsv"
    path.write_text("# origin: klingon\nа\tа\ts\thand_written\n", encoding="utf-8")
    assert read_gold_origin(path) is None


@pytest.mark.parametrize(
    ("origin", "direction", "independent"),
    [
        (Orthography.NARKAMAUKA, N2T, True),  # source side was authored: accuracy
        (Orthography.NARKAMAUKA, T2N, False),  # source side was derived: consistency
        (Orthography.TARASKIEVICA, T2N, True),
        (Orthography.TARASKIEVICA, N2T, False),
    ],
)
def test_report_knows_which_direction_is_evidence(
    converter: Converter, origin: Orthography, direction: Orthography, independent: bool
) -> None:
    report = evaluate(converter, [("снег", "сьнег")], direction, origin=origin)
    assert report.is_independent is independent


def test_report_without_origin_is_not_claimed_independent(converter: Converter) -> None:
    """Unknown must not read as a clean bill of health."""
    report = evaluate(converter, [("снег", "сьнег")], N2T)
    assert report.origin is None
    assert not report.is_independent


# --- proposed rows are never scored ---------------------------------------------------------
def test_proposed_is_unscored() -> None:
    assert PROPOSED in UNSCORED
    assert PROPOSED in PROVENANCES


def test_proposed_rows_are_excluded_from_scoring(tmp_path: Path) -> None:
    """Scoring a converter proposal against the converter returns 100% by construction."""
    path = tmp_path / "g.tsv"
    path.write_text(
        "# origin: taraskievica\n"
        "снег\tсьнег\tbetarask:X@1\tproposed\n"
        "свет\tсьвет\tbetarask:X@1\thand_written\n",
        encoding="utf-8",
    )
    assert read_gold(path) == [("свет", "сьвет")]


def test_the_shipped_independent_gold_is_all_proposals_for_now() -> None:
    """Until a human reviews them, this file must score nothing at all."""
    rows = read_gold_rows(GOLD_T2N)
    assert rows, "gold_t2n.tsv is empty"
    reviewed = [r for r in rows if r.provenance != PROPOSED]
    assert read_gold(GOLD_T2N) == [
        (r.narkamauka, r.taraskievica) for r in reviewed if r.provenance not in UNSCORED
    ]


def test_independent_gold_rows_are_well_formed() -> None:
    for row in read_gold_rows(GOLD_T2N):
        assert row.provenance in PROVENANCES, row.provenance
        assert row.source.startswith("betarask:"), row.source
        assert "@" in row.source, f"{row.source} has no revision id"
        assert row.narkamauka and row.taraskievica


# --- the corpus ------------------------------------------------------------------------------
def test_corpus_rows_carry_attribution() -> None:
    rows = read_corpus(CORPUS)
    assert len(rows) >= 100, f"only {len(rows)} sentences"
    for row in rows:
        assert row.article, row.sentence
        assert row.revid.isdigit(), f"{row.article}: revid {row.revid!r}"


def test_corpus_sentences_all_carry_a_taraskievica_marker() -> None:
    """A sentence that reads the same in both orthographies would pad the denominator."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from fetch_tarask_corpus import has_marker

    missing = [r.sentence for r in read_corpus(CORPUS) if not has_marker(r.sentence)]
    assert not missing, f"{len(missing)} sentences with nothing to convert: {missing[:3]}"


def test_corpus_licence_is_recorded() -> None:
    readme = (TARASK / "README.md").read_text(encoding="utf-8")
    assert "CC BY-SA 4.0" in readme
    assert "be-tarask.wikipedia.org" in readme


# --- the audit -------------------------------------------------------------------------------
def test_audit_groups_by_distinct_change(converter: Converter) -> None:
    rows = audit_changes(converter, ["сьнег і сьвет", "сьнег зноў"], T2N)
    snieh = [r for r in rows if r.source == "сьнег"]
    assert len(snieh) == 1, "the same change must be one row to review, not two"
    assert snieh[0].count == 2


def test_audit_is_ordered_by_frequency(converter: Converter) -> None:
    rows = audit_changes(converter, ["сьнег сьнег сьнег", "сьвет"], T2N)
    counts = [r.count for r in rows]
    assert counts == sorted(counts, reverse=True)


def test_audit_records_an_example_sentence(converter: Converter) -> None:
    rows = audit_changes(converter, ["сьнег ідзе"], T2N)
    assert all(r.example for r in rows)


def test_precision_is_none_before_review() -> None:
    """Not 0.0, and emphatically not 1.0."""
    report = audit_precision([AuditRow("сьнег", "снег", "r", 3)])
    assert report.precision is None
    assert report.unreviewed_tokens == 3


def test_precision_is_token_weighted() -> None:
    """A wrong change occurring 10 times should hurt more than one occurring once."""
    report = audit_precision(
        [
            AuditRow("a", "b", "r", 90, verdict=OK),
            AuditRow("c", "d", "r", 10, verdict=WRONG),
        ]
    )
    assert report.precision == pytest.approx(0.9)


def test_unsure_is_excluded_from_precision_but_counted() -> None:
    report = audit_precision(
        [
            AuditRow("a", "b", "r", 1, verdict=OK),
            AuditRow("c", "d", "r", 99, verdict="unsure"),
        ]
    )
    assert report.precision == 1.0
    assert report.unsure_tokens == 99
    assert report.reviewed_share == 1.0


def test_merge_keeps_verdicts_and_refreshes_counts() -> None:
    existing = {("a", "b", "r"): AuditRow("a", "b", "r", 1, verdict=OK, note="cited §11б")}
    merged = merge_audit([AuditRow("a", "b", "r", 7)], existing)
    assert merged[0].count == 7
    assert merged[0].verdict == OK
    assert merged[0].note == "cited §11б"


def test_merge_drops_changes_the_converter_no_longer_makes() -> None:
    """A verdict on a change that no longer happens would keep skewing the number."""
    existing = {("gone", "x", "r"): AuditRow("gone", "x", "r", 5, verdict=WRONG)}
    assert merge_audit([AuditRow("a", "b", "r", 1)], existing) == [AuditRow("a", "b", "r", 1)]


def test_audit_round_trips_through_a_file(tmp_path: Path) -> None:
    path = tmp_path / "audit.tsv"
    rows = [AuditRow("сьнег", "снег", "palat.unassim", 4, verdict=OK, note="n", example="e")]
    write_audit(rows, path)
    assert read_audit(path)[("сьнег", "снег", "palat.unassim")] == rows[0]


def test_shipped_audit_verdicts_are_valid() -> None:
    audit = TARASK / "audit.tsv"
    if not audit.is_file():
        pytest.skip("no audit file yet")
    for row in read_audit(audit).values():
        assert row.verdict in VERDICTS, f"{row.source}->{row.target}: {row.verdict!r}"


#: Measured 95.05% once the audit was fully reviewed (408 ok / 28 wrong / 2 unsure over
#: 437 distinct changes). The floor sits a point below that as a ratchet: raise it as the
#: `wrong` rows get fixed in the converter, never lower it to make a change pass.
AUDITED_PRECISION_FLOOR = 0.94


def test_audited_precision_does_not_regress() -> None:
    """CI gate. Inert until rows are reviewed, then it holds the line."""
    audit = TARASK / "audit.tsv"
    if not audit.is_file():
        pytest.skip("no audit file yet")
    report = audit_precision(read_audit(audit).values())
    if report.precision is None:
        pytest.skip(f"nothing reviewed yet ({report.distinct} changes await a verdict)")
    assert report.precision >= AUDITED_PRECISION_FLOOR, (
        f"precision {report.precision:.1%} on genuine Taraškievica "
        f"({report.wrong_tokens} wrong of {report.scored_tokens} reviewed tokens)"
    )


# --- held out --------------------------------------------------------------------------------
def test_independent_gold_is_held_out() -> None:
    """Same rule as gold.tsv: nothing that builds data may read the evaluation set."""
    for path in (
        ROOT / "src" / "pravapis" / "lexicon" / "builder.py",
        ROOT / "src" / "pravapis" / "lexicon" / "stems.py",
        ROOT / "scripts" / "build_lexicon.py",
        ROOT / "scripts" / "mine_loan_stems.py",
        ROOT / "scripts" / "align_corpora.py",
    ):
        text = path.read_text(encoding="utf-8").lower()
        assert "tarask/" not in text and "gold_t2n" not in text, path


def test_trusted_subset_of_independent_gold_is_empty_until_reviewed() -> None:
    assert read_gold(GOLD_T2N, trusted_only=True) == [
        (r.narkamauka, r.taraskievica)
        for r in read_gold_rows(GOLD_T2N)
        if r.provenance == HAND_WRITTEN
    ]


# --- the review workflow ---------------------------------------------------------------
def test_sample_spreads_across_the_selection() -> None:
    """A sample used to justify accepting a whole rule must not be the frequent rows only.

    Those are the ones most likely to be right, so sampling the top would be sampling
    exactly the evidence that cannot falsify the class.
    """
    from pravapis.cli import _spread

    rows = [AuditRow(f"s{i}", f"t{i}", "r", 100 - i) for i in range(100)]
    picked = _spread(rows, 5)
    assert len(picked) == 5
    assert picked[0].source == "s0"
    assert picked[-1].source != "s4", "a spread sample must reach the tail"
    assert [r.source for r in picked] == ["s0", "s20", "s40", "s60", "s80"]


def test_spread_returns_everything_when_asked_for_more_than_exists() -> None:
    from pravapis.cli import _spread

    rows = [AuditRow("a", "b", "r", 1)]
    assert _spread(rows, 10) == rows


def _run(args: list[str]) -> tuple[int, str]:
    from typer.testing import CliRunner

    from pravapis.cli import app

    result = CliRunner().invoke(app, args)
    return result.exit_code, result.output


def test_bulk_mark_refuses_without_a_rule_filter(tmp_path: Path) -> None:
    """Grading every change in one command is never what someone means."""
    out = tmp_path / "a.tsv"
    code, output = _run(
        ["audit", str(CORPUS), "--to", "narkamauka", "--mark", "ok", "-o", str(out)]
    )
    assert code != 0
    assert "--rule" in output
    assert not out.exists()


def test_bulk_mark_refuses_an_unknown_verdict(tmp_path: Path) -> None:
    code, output = _run(
        [
            "audit",
            str(CORPUS),
            "--to",
            "narkamauka",
            "--rule",
            "palat.",
            "--mark",
            "probably",
            "-o",
            str(tmp_path / "a.tsv"),
        ]
    )
    assert code != 0
    assert "ok" in output and "wrong" in output


def test_bulk_mark_refuses_without_somewhere_to_record_it() -> None:
    code, output = _run(
        ["audit", str(CORPUS), "--to", "narkamauka", "--rule", "palat.", "--mark", "ok"]
    )
    assert code != 0
    assert "--out" in output


def test_bulk_mark_scopes_to_the_rule_and_spares_other_verdicts(tmp_path: Path) -> None:
    out = tmp_path / "a.tsv"
    code, _ = _run(
        [
            "audit",
            str(CORPUS),
            "--to",
            "narkamauka",
            "--rule",
            "palat.unassim",
            "--mark",
            "ok",
            "--note",
            "sampled",
            "-o",
            str(out),
        ]
    )
    assert code == 0
    rows = read_audit(out).values()
    marked = [r for r in rows if r.verdict]
    assert marked, "nothing was marked"
    assert all("palat.unassim" in r.rule for r in marked)
    assert all(r.verdict == OK and r.note == "sampled" for r in marked)
    assert any(not r.verdict for r in rows), "rows outside the rule must stay unreviewed"


def test_rerunning_keeps_recorded_verdicts(tmp_path: Path) -> None:
    out = tmp_path / "a.tsv"
    _run(
        [
            "audit",
            str(CORPUS),
            "--to",
            "narkamauka",
            "--rule",
            "loan.",
            "--mark",
            "ok",
            "-o",
            str(out),
        ]
    )
    before = {k: v.verdict for k, v in read_audit(out).items() if v.verdict}
    _run(["audit", str(CORPUS), "--to", "narkamauka", "-o", str(out)])
    after = {k: v.verdict for k, v in read_audit(out).items() if v.verdict}
    assert before == after


#: Rows that are `proposed` for a reason, and the reason. A row listed here is one
#: nobody can review as it stands — not one nobody has got to yet — so it is named
#: rather than left to soften the gate below.
KNOWN_UNREVIEWED: Final[dict[str, str]] = {
    "betarask:Pink Floyd@2309770": (
        "the Narkamaŭka column is the single character 'n' — the row was truncated at "
        "some point and the original text is not recoverable from the file. Needs a "
        "human to write the Narkamaŭka side of the Taraškievica sentence."
    ),
}


def test_independent_gold_is_fully_reviewed() -> None:
    """gold_t2n.tsv exists to give a T → N figure; `proposed` rows give none.

    The allowance is an explicit list of sources with a reason each, so a row that is
    merely unfinished still fails here. A test that counted `proposed` rows against a
    threshold would let a corrupt row and a lazy one look the same.
    """
    rows = read_gold_rows(GOLD_T2N)
    proposed = [r for r in rows if r.provenance == PROPOSED]
    unexpected = [r for r in proposed if r.source not in KNOWN_UNREVIEWED]
    assert not unexpected, (
        f"{len(unexpected)} of {len(rows)} rows are unreviewed and not accounted for:\n  "
        + "\n  ".join(r.source for r in unexpected)
        + "\n\nReview the row, or add it to KNOWN_UNREVIEWED with the reason it cannot be."
    )
    stale = [src for src in KNOWN_UNREVIEWED if src not in {r.source for r in proposed}]
    assert not stale, f"reviewed now, so drop from KNOWN_UNREVIEWED: {stale}"


def test_independent_t2n_accuracy_does_not_regress(converter: Converter) -> None:
    """The number Phase C was built to produce.

    Measured 94.3% change accuracy against genuine be-tarask text, versus 99.0% on the
    derived gold set — the gap is the whole point of having this file. The floor is a
    ratchet; raise it as the converter improves.
    """
    report = evaluate(
        converter,
        read_gold(GOLD_T2N, trusted_only=True),
        Orthography.NARKAMAUKA,
        origin=Orthography.TARASKIEVICA,
    )
    assert report.is_independent
    assert report.change_accuracy >= 0.93, report.change_accuracy
    assert report.false_positive_rate == 0.0, report.false_positive_rate


def test_audit_describes_changes_the_converter_actually_makes(converter: Converter) -> None:
    """Every audit row must correspond to a change the converter really produces.

    The `source` and `target` columns are a *record*, not a worksheet: they say what the
    converter did. Editing them — correcting a word in place rather than recording a
    verdict on it — leaves a row describing something that never happened, and precision
    is then computed over rows that cannot be right or wrong. A row with `source ==
    target` is the clearest case: that is not a change at all.

    To act on a wrong conversion, fix the converter (stems.tsv, the lexicon, a rule) and
    re-run `pravapis audit`, which drops the row by itself.
    """
    on_file = read_audit(TARASK / "audit.tsv")
    produced = {
        r.key
        for r in audit_changes(
            converter,
            [row.sentence for row in read_corpus(CORPUS)],
            Orthography.NARKAMAUKA,
        )
    }
    identity = [k for k in on_file if k[0] == k[1]]
    assert not identity, (
        f"{len(identity)} audit row(s) have source == target, which is not a change: {identity[:5]}"
    )
    stale = sorted(set(on_file) - produced)
    assert not stale, (
        f"{len(stale)} audit row(s) describe changes the converter does not make — "
        f"re-run `pravapis audit -o data/eval/tarask/audit.tsv` to resync: {stale[:5]}"
    )


def test_independent_gold_taraskievica_column_is_the_untouched_corpus() -> None:
    """The Taraškievica side of gold_t2n.tsv must be the corpus sentence, character for
    character.

    The file's header promises that column is genuine be-tarask.wikipedia.org text, not
    derived from any Narkamaŭka source, and the whole point of the independent T → N
    figure rests on it. 28 rows had drifted: і → ы in агрэсыі, Азыі, Азыяцкай, гімназыя,
    дывізыя, і → й from the optional §13 rule, inserted ь, and vocabulary swapped for a
    preferred synonym — every one of them a change this converter makes. Gold edited
    toward the converter measures the converter against itself, which is the mistake
    data/eval/gold.tsv already exists to document.
    """
    corpus = {row.sentence for row in read_corpus(CORPUS)}
    rows = read_gold_rows(GOLD_T2N)
    drifted = [r.taraskievica for r in rows if r.taraskievica and r.taraskievica not in corpus]
    assert not drifted, (
        f"{len(drifted)} gold_t2n row(s) have a Taraškievica column that is not in "
        f"{CORPUS.name} verbatim: {drifted[:3]}"
    )
