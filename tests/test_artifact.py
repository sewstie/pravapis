from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pravapis.artifact import (
    ARTIFACT_SCHEMA,
    ArtifactError,
    ConverterArtifact,
    artifact_filename,
    build_artifact,
    load_artifact,
    validate_manifest_files,
)
from pravapis.dataversion import compute_data_hash, read_manifest
from pravapis.types import Orthography


def test_validate_manifest_files_has_no_problems(data_dir: Path) -> None:
    assert validate_manifest_files(data_dir) == []


def test_build_artifact_is_named_by_the_data_hash(data_dir: Path, tmp_path: Path) -> None:
    """The cross-check: whatever GET /v1/version reports as data_hash (it calls the same
    compute_data_hash the artifact builder does) must equal the hash the artifact's own
    filename carries, for the same data tree."""
    out = build_artifact(data_dir, tmp_path)
    assert out.name == artifact_filename(compute_data_hash(data_dir))


def test_artifact_round_trips_to_a_working_converter(data_dir: Path, tmp_path: Path) -> None:
    out = build_artifact(data_dir, tmp_path)
    artifact = load_artifact(out)
    assert isinstance(artifact, ConverterArtifact)
    assert artifact.schema == ARTIFACT_SCHEMA
    assert artifact.data_hash == compute_data_hash(data_dir)

    converter = artifact.converter()
    result = converter.convert("Снег і план", Orthography.TARASKIEVICA)
    assert result.text == "Сьнег і плян"


def test_load_artifact_rejects_a_non_artifact_file(tmp_path: Path) -> None:
    bogus = tmp_path / "pravapis-deadbeef.bin"
    bogus.write_bytes(b"not a pickle of a ConverterArtifact")
    with pytest.raises(ArtifactError):
        load_artifact(bogus)


def _copy_manifest_tree(src_root: Path, dst_root: Path) -> None:
    for rel in read_manifest(src_root):
        src = src_root / rel
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    shutil.copy2(src_root / "MANIFEST", dst_root / "MANIFEST")
    shutil.copy2(src_root / "VERSION", dst_root / "VERSION")
    # validate_manifest_files reads the *original* data_dir, schemas included — the
    # manifest-only clean room build_artifact constructs internally never needs them.
    shutil.copytree(src_root / "schemas", dst_root / "schemas")


def test_committed_artifact_is_not_stale(data_dir: Path, tmp_path: Path) -> None:
    """data/pravapis-<hash>.bin is committed — this deployment has no build step, so
    Vercel gets whatever is in git. Regenerating from today's data must reproduce it
    exactly, the same check test_conformance.py runs for conformance/cases.jsonl. If
    this fails, the data changed and nobody ran `pravapis build-artifact` and
    committed the result — deployed behaviour is one commit behind the data.
    """
    committed = sorted(data_dir.glob("pravapis-*.bin"))
    if not committed:
        pytest.skip("no committed artifact yet")
    fresh = build_artifact(data_dir, tmp_path)
    assert fresh.name == committed[0].name, (
        f"data/MANIFEST changed since {committed[0].name} was built "
        f"(fresh hash is in {fresh.name}) — rebuild and commit it"
    )
    assert fresh.read_bytes() == committed[0].read_bytes(), (
        f"{committed[0]} is stale — run `pravapis build-artifact` and commit the result"
    )


def test_a_stray_file_outside_the_manifest_does_not_change_the_artifact(
    data_dir: Path, tmp_path: Path
) -> None:
    """A file sitting in data/lexicon/stems/ that data/MANIFEST does not list must not
    affect the build at all — not the trie, not the rules, not one byte of the artifact.
    Two identically-named artifacts that were not byte-identical would be exactly the
    silent divergence data/MANIFEST exists to rule out."""
    clean = tmp_path / "clean"
    dirty = tmp_path / "dirty"
    _copy_manifest_tree(data_dir, clean)
    _copy_manifest_tree(data_dir, dirty)

    stray = dirty / "lexicon" / "stems" / "not_in_manifest.tsv"
    stray.write_text(
        "#!schema tag:pravapis,2026:schema:stems:1\n"
        "#!columns\tstem\tclass\talternations\n"
        "нечакан\tloan\te\n",
        encoding="utf-8",
    )

    clean_out = build_artifact(clean, tmp_path / "clean-out")
    dirty_out = build_artifact(dirty, tmp_path / "dirty-out")

    assert clean_out.name == dirty_out.name
    assert clean_out.read_bytes() == dirty_out.read_bytes()
