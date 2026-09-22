from __future__ import annotations

from pathlib import Path

import pytest

from pravapis.dataversion import (
    DataVersionError,
    check_data_version,
    compute_data_hash,
    read_data_version,
)
from pravapis.lexicon.builder import (
    build_from_sources,
    save_lexicon,
    sources_digest,
    write_data_hash_marker,
)


def test_read_data_version(data_dir: Path) -> None:
    assert read_data_version(data_dir) == "1.3.0"


def test_check_data_version_matches(data_dir: Path) -> None:
    assert check_data_version(data_dir, implemented="1.3.0") is None


def test_check_data_version_minor_ahead(data_dir: Path, tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.9.0\n", encoding="utf-8")
    note = check_data_version(tmp_path, implemented="1.3.0")
    assert note is not None and "1.9.0" in note


def test_check_data_version_major_mismatch(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("2.0.0\n", encoding="utf-8")
    with pytest.raises(DataVersionError):
        check_data_version(tmp_path, implemented="1.3.0")


def test_compute_data_hash_is_deterministic(data_dir: Path) -> None:
    assert compute_data_hash(data_dir) == compute_data_hash(data_dir)


def test_compute_data_hash_reads_manifest_order(tmp_path: Path) -> None:
    (tmp_path / "a.tsv").write_text("a", encoding="utf-8")
    (tmp_path / "b.tsv").write_text("b", encoding="utf-8")
    (tmp_path / "MANIFEST").write_text("a.tsv\nb.tsv\n", encoding="utf-8")
    forward = compute_data_hash(tmp_path)

    (tmp_path / "MANIFEST").write_text("b.tsv\na.tsv\n", encoding="utf-8")
    reversed_order = compute_data_hash(tmp_path)

    assert forward != reversed_order


def test_compute_data_hash_skips_comments_and_blank_lines(tmp_path: Path) -> None:
    (tmp_path / "a.tsv").write_text("a", encoding="utf-8")
    (tmp_path / "MANIFEST").write_text("a.tsv\n", encoding="utf-8")
    plain = compute_data_hash(tmp_path)

    (tmp_path / "MANIFEST").write_text("# a comment\n\na.tsv\n\n", encoding="utf-8")
    with_comments = compute_data_hash(tmp_path)

    assert plain == with_comments


def test_compute_data_hash_changes_with_listed_file(tmp_path: Path) -> None:
    (tmp_path / "a.tsv").write_text("a", encoding="utf-8")
    (tmp_path / "MANIFEST").write_text("a.tsv\n", encoding="utf-8")
    before = compute_data_hash(tmp_path)

    (tmp_path / "a.tsv").write_text("a-changed", encoding="utf-8")
    after = compute_data_hash(tmp_path)

    assert before != after


def test_compute_data_hash_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(DataVersionError):
        compute_data_hash(tmp_path)


def test_compute_data_hash_missing_listed_file(tmp_path: Path) -> None:
    (tmp_path / "MANIFEST").write_text("nope.tsv\n", encoding="utf-8")
    with pytest.raises(DataVersionError):
        compute_data_hash(tmp_path)


def test_build_artifact_hash_matches_data_hash(data_dir: Path, tmp_path: Path) -> None:
    """The cross-check: whatever /v1/version reports as data_hash must equal the
    hash a fresh build stamps onto its own artifact's filename. Two independent
    computations of "the data hash" agreeing is exactly the property that would
    have caught two branches silently diverging on what "the data" is."""
    lexicon_src = data_dir / "lexicon"
    fwd, rev = build_from_sources(lexicon_src)
    out = tmp_path / "lexicon.marisa"
    save_lexicon(fwd, rev, out, source_digest=sources_digest(lexicon_src))

    marker = write_data_hash_marker(out, data_dir)

    embedded_hash = marker.name.removeprefix("lexicon-").removesuffix(".built")
    assert embedded_hash == compute_data_hash(data_dir)
