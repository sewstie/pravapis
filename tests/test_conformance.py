"""The committed conformance corpus is current, and it actually holds.

Two independent claims, both worth testing:

* the corpus on disk is what today's data would generate — otherwise it certifies
  behaviour the project no longer has;
* every case in it passes when replayed — otherwise the contract a port is asked to
  meet is one the reference implementation does not meet either.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pravapis.conformance import build_corpus, write_jsonl
from pravapis.pipeline import Converter
from pravapis.rules.engine import RuleEngine, load_rules
from pravapis.translit import Transliterator
from pravapis.translit.engine import load_scheme
from pravapis.types import Orthography

CASE_FIELDS = {"id", "kind", "direction", "script", "rule", "in", "out"}
DIRECTIONS = {
    "narkamauka_to_taraskievica": Orthography.TARASKIEVICA,
    "taraskievica_to_narkamauka": Orthography.NARKAMAUKA,
}


@pytest.fixture(scope="module")
def corpus_dir(data_dir: Path) -> Path:
    return data_dir.parent / "conformance"


@pytest.fixture(scope="module")
def cases(corpus_dir: Path) -> list[dict[str, object]]:
    text = (corpus_dir / "cases.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_corpus_is_committed(corpus_dir: Path) -> None:
    assert (corpus_dir / "cases.jsonl").is_file()
    assert (corpus_dir / "manifest.json").is_file()


def test_every_record_has_exactly_the_frozen_fields(cases: list[dict[str, object]]) -> None:
    for case in cases:
        extra = set(case) - CASE_FIELDS
        assert not extra, f"{case['id']}: unexpected field(s) {sorted(extra)}"
        assert {"id", "kind", "direction", "script", "in", "out"} <= set(case)


def test_corpus_is_not_stale(data_dir: Path, tmp_path: Path, corpus_dir: Path) -> None:
    """Regenerating from today's data must reproduce the committed bytes, exactly.

    This is the same check CI runs. If it fails, the data changed and nobody ran
    `pravapis export-conformance` — so the committed contract describes the old
    behaviour, which is worse than having no contract at all.
    """
    fresh, _ = build_corpus(data_dir)
    write_jsonl(fresh, tmp_path / "cases.jsonl")
    assert (tmp_path / "cases.jsonl").read_bytes() == (corpus_dir / "cases.jsonl").read_bytes(), (
        "conformance/cases.jsonl is stale — run `pravapis export-conformance` and commit it"
    )


def test_manifest_hash_matches_the_corpus(corpus_dir: Path) -> None:
    import hashlib

    manifest = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256((corpus_dir / "cases.jsonl").read_bytes()).hexdigest()
    assert manifest["sha256"] == digest
    assert manifest["cases"] == len(
        (corpus_dir / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    )


def test_manifest_records_the_data_version(corpus_dir: Path, data_dir: Path) -> None:
    from pravapis.dataspec import read_data_version

    manifest = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_version"] == read_data_version(data_dir)


# --- replay: the contract holds for the reference implementation -----------------
def test_every_case_passes_when_replayed(
    cases: list[dict[str, object]], converter: Converter, data_dir: Path
) -> None:
    """Run each case the way its `kind` says a port should, and compare."""
    rules = {
        rule.id: rule
        for path in sorted((data_dir / "rules").glob("*.yaml"))
        for rule in load_rules(path)
    }
    schemes = {
        load_scheme(path).name: load_scheme(path)
        for path in sorted((data_dir / "translit").glob("*.yaml"))
    }
    failures: list[str] = []
    for case in cases:
        kind, source, expected = case["kind"], str(case["in"]), str(case["out"])
        if kind == "rule":
            rule = rules[str(case["rule"])]
            engine = RuleEngine([rule], include_optional=True, stems=converter.engine.stems)
            got, _ = engine.apply(source, rule.direction)
        elif kind == "translit":
            got = Transliterator(schemes[str(case["script"])]).transliterate(source).text
        else:
            got = converter.convert(source, DIRECTIONS[str(case["direction"])]).text
        if got != expected:
            failures.append(f"{case['id']}: {source!r} gave {got!r}, contract says {expected!r}")
    assert not failures, "\n".join(failures[:15])


def test_known_failures_really_do_fail(corpus_dir: Path, converter: Converter) -> None:
    """Otherwise they belong in the contract, not in the list of gaps."""
    path = corpus_dir / "known_failures.jsonl"
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for case in rows:
        if case["kind"] in {"gold", "heldout"}:
            got = converter.convert(case["in"], DIRECTIONS[case["direction"]]).text
            assert got != case["out"], (
                f"{case['id']} now passes — move it into cases.jsonl by regenerating"
            )


def test_gold_cases_are_exported_in_one_direction_only(cases: list[dict[str, object]]) -> None:
    """gold.tsv is narkamauka-origin, so T → N from it would be self-consistency."""
    gold = {c["direction"] for c in cases if c["kind"] == "gold"}
    heldout = {c["direction"] for c in cases if c["kind"] == "heldout"}
    assert gold == {"narkamauka_to_taraskievica"}
    assert heldout == {"taraskievica_to_narkamauka"}


def test_rule_cases_name_their_rule(cases: list[dict[str, object]]) -> None:
    for case in cases:
        if case["kind"] == "rule":
            assert case.get("rule"), f"{case['id']} has no rule"
        if case["kind"] == "translit":
            assert case["direction"] is None
