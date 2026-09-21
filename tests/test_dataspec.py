"""The data validates against its own schemas — and the schemas can actually fail.

A validator that passes everything is worth nothing, so most of this file is negative
controls: each one breaks a shipped data file in one specific way and asserts that
`pravapis validate-data` notices. If one of these starts passing, the schema has a
hole in exactly the place the test names.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pravapis.dataspec import (
    DATA_VERSION,
    DataVersionError,
    check_data_version,
    read_data_version,
    validate_corpus_file,
    validate_data,
    validate_rules_file,
    validate_scheme_file,
    validate_stems_file,
)
from pravapis.lexicon.stems import DECLARED_COLUMNS, SCHEMA_ID, read_declaration
from pravapis.rules.engine import load_rules

pytest.importorskip("jsonschema", reason="data validation needs pravapis[spec]")


def test_shipped_data_is_valid(data_dir: Path) -> None:
    problems = validate_data(data_dir)
    assert problems == [], "\n".join(str(p) for p in problems)


# --- versioning ------------------------------------------------------------------
def test_data_version_is_semver(data_dir: Path) -> None:
    major, minor, patch = read_data_version(data_dir).split(".")
    assert all(part.isdigit() for part in (major, minor, patch))


def test_this_build_implements_the_shipped_data(data_dir: Path) -> None:
    assert check_data_version(data_dir) is None


def test_major_mismatch_is_fatal(data_dir: Path) -> None:
    with pytest.raises(DataVersionError, match="Major versions differ"):
        check_data_version(data_dir, implemented="99.0.0")


def test_data_minor_ahead_is_a_note_not_an_error(data_dir: Path) -> None:
    """Minor bumps are additive, so older code reads newer data correctly."""
    major = read_data_version(data_dir).split(".")[0]
    note = check_data_version(data_dir, implemented=f"{major}.0.0")
    on_disk_minor = int(read_data_version(data_dir).split(".")[1])
    if on_disk_minor > 0:
        assert note is not None and "additive" in note
    else:
        assert note is None


# --- every rule is citable -------------------------------------------------------
def test_every_rule_carries_a_citation(data_dir: Path) -> None:
    for path in sorted((data_dir / "rules").glob("*.yaml")):
        for rule in load_rules(path):
            assert rule.citation, f"{path.name}: rule {rule.id} has no citation"


def test_stems_file_declares_its_schema_and_columns(data_dir: Path) -> None:
    declaration = read_declaration(data_dir / "lexicon" / "stems" / "stems.tsv")
    assert declaration.schema == SCHEMA_ID
    assert declaration.columns == DECLARED_COLUMNS


# --- negative controls: rule files -----------------------------------------------
def _rules_text(data_dir: Path) -> str:
    return (data_dir / "rules" / "palatalization.yaml").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("label", "old", "new"),
    [
        ("missing citation", '    citation: "Збор 2005, §29, §43"\n', ""),
        ("citation that cites nothing", 'citation: "Збор 2005, §40"', 'citation: "trust me"'),
        ("typo'd key", "    priority: 120\n", "    priority: 120\n    prioritt: 5\n"),
        ("unknown direction", "direction: narkamauka_to_taraskievica", "direction: n2tarask"),
        (
            "no description",
            '    description: "Soft geminate дз: суддзя → судзьдзя; not at a prefix boundary (аддзел)"\n',
            "",
        ),
    ],
)
def test_broken_rule_file_is_caught(
    data_dir: Path, tmp_path: Path, label: str, old: str, new: str
) -> None:
    broken = tmp_path / "broken.yaml"
    text = _rules_text(data_dir)
    assert old in text, f"fixture drifted: {label!r} no longer matches the shipped file"
    broken.write_text(text.replace(old, new, 1), encoding="utf-8")
    assert validate_rules_file(broken, data_dir), f"{label} was not caught"


def test_rule_whose_own_test_is_wrong_is_caught(data_dir: Path, tmp_path: Path) -> None:
    """Inline cases are exported into the conformance corpus; a wrong one would be inherited."""
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        _rules_text(data_dir).replace(
            '{ input: "снег", expected: "сьнег" }', '{ input: "снег", expected: "снех" }'
        ),
        encoding="utf-8",
    )
    problems = validate_rules_file(broken, data_dir)
    assert any("positive test" in p.message for p in problems)


# --- negative controls: the stem inventory ---------------------------------------
def _stems_text(data_dir: Path) -> str:
    return (data_dir / "lexicon" / "stems" / "stems.tsv").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("label", "extra"),
    [
        ("native stem that licenses an alternation", "лапа\tnative\tl\t§55.1\tcited\n"),
        ("loan stem that can never fire", "шмуляк\tloan\t-\t§55.1\tcited\n"),
        ("loan stem marked cited with no source", "шмуляк\tloan\tl\t-\tcited\n"),
        ("unknown alternation code", "шмуляк\tloan\tz\t§55.1\tcited\n"),
        ("unknown provenance", "шмуляк\tloan\tl\t§55.1\tprobably\n"),
    ],
)
def test_bad_stem_row_is_caught(data_dir: Path, tmp_path: Path, label: str, extra: str) -> None:
    broken = tmp_path / "stems.tsv"
    broken.write_text(_stems_text(data_dir) + extra, encoding="utf-8")
    assert validate_stems_file(broken, data_dir), f"{label} was not caught"


def test_undeclared_stems_file_is_caught(data_dir: Path, tmp_path: Path) -> None:
    broken = tmp_path / "stems.tsv"
    broken.write_text(
        _stems_text(data_dir).replace(f"#!schema {SCHEMA_ID}\n", "", 1), encoding="utf-8"
    )
    problems = validate_stems_file(broken, data_dir)
    assert any("#!schema" in p.message for p in problems)


def test_reordered_columns_are_caught(data_dir: Path, tmp_path: Path) -> None:
    """The declaration is the point: a file that reorders its columns must say so and fail."""
    broken = tmp_path / "stems.tsv"
    broken.write_text(
        _stems_text(data_dir).replace("#!columns stem\tclass", "#!columns class\tstem", 1),
        encoding="utf-8",
    )
    problems = validate_stems_file(broken, data_dir)
    assert any("orders them" in p.message for p in problems)


# --- negative controls: transliteration schemes ----------------------------------
def _scheme_text(data_dir: Path) -> str:
    return (data_dir / "translit" / "lacinka.yaml").read_text(encoding="utf-8")


def test_condition_outside_the_closed_vocabulary_is_caught(data_dir: Path, tmp_path: Path) -> None:
    broken = tmp_path / "scheme.yaml"
    broken.write_text(
        _scheme_text(data_dir).replace("when: before_soft_vowel", "when: before_softish", 1),
        encoding="utf-8",
    )
    assert validate_scheme_file(broken, data_dir)


def test_scheme_that_cannot_consume_a_letter_is_caught(data_dir: Path, tmp_path: Path) -> None:
    broken = tmp_path / "scheme.yaml"
    text = _scheme_text(data_dir)
    assert '  - { from: "ж", to: "ž" }\n' in text
    broken.write_text(text.replace('  - { from: "ж", to: "ž" }\n', "", 1), encoding="utf-8")
    problems = validate_scheme_file(broken, data_dir)
    assert any("no mapping consumes" in p.message for p in problems)


# --- the corpus validates against its own schema ---------------------------------
def test_corpus_records_match_the_conformance_schema(data_dir: Path) -> None:
    corpus = data_dir.parent / "conformance" / "cases.jsonl"
    assert corpus.is_file(), "conformance/cases.jsonl is not committed"
    problems = validate_corpus_file(corpus, data_dir)
    assert problems == [], "\n".join(str(p) for p in problems[:10])


def test_data_version_constant_is_reachable_from_the_package() -> None:
    import pravapis

    assert pravapis.DATA_VERSION == DATA_VERSION
