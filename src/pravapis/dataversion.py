"""Which version of the data this build implements, and whether it can read what it found.

Kept deliberately small and dependency-free, separate from :mod:`pravapis.dataspec`.
Declaring and checking the data version is a *runtime* concern — the deployed function
should be able to say which data it is serving — while validating data against the
JSON Schemas is a development and CI concern that pulls in ``jsonschema`` and every
parser in the project. Putting both in one module would drag the second into the first.

See data/VERSIONING.md for what a major and a minor bump mean.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

import regex

from pravapis.config import find_data_dir

#: The data version this code implements. Every implementation — this one, a port —
#: declares its own; the conformance corpus records the version it was generated from.
DATA_VERSION: Final[str] = "1.3.0"

_SEMVER: Final[regex.Pattern[str]] = regex.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class DataVersionError(RuntimeError):
    """The data on disk is not a version this code can read."""


def read_data_version(root: Path | None = None) -> str:
    """The content version of the data package, from ``data/VERSION``."""
    path = (root or find_data_dir()) / "VERSION"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DataVersionError(f"{path}: cannot read the data version: {exc}") from exc
    version = next(
        (ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.startswith("#")), ""
    )
    if not _SEMVER.match(version):
        raise DataVersionError(f"{path}: {version!r} is not a semver triple")
    return version


def check_data_version(root: Path | None = None, *, implemented: str = DATA_VERSION) -> str | None:
    """Compare the data on disk against the version this code implements.

    A **major** difference is fatal: the data uses a shape this code does not
    understand, or vice versa, and converting anyway would produce answers that look
    fine and are not. A **minor** difference is not — minor bumps are additive (a stem
    added, an optional field), so older code reads newer data correctly, it simply does
    not exercise all of it. That case returns a note rather than raising.
    """
    on_disk = read_data_version(root)
    theirs, ours = _SEMVER.match(on_disk), _SEMVER.match(implemented)
    assert theirs is not None
    if ours is None:
        raise DataVersionError(f"implemented version {implemented!r} is not a semver triple")
    if theirs.group(1) != ours.group(1):
        raise DataVersionError(
            f"data/VERSION is {on_disk}, but this build implements data version "
            f"{implemented}. Major versions differ, so the data's shape is not the shape "
            f"this code reads. Upgrade one of them; see data/VERSIONING.md."
        )
    if int(theirs.group(2)) > int(ours.group(2)):
        return (
            f"data/VERSION is {on_disk}; this build implements {implemented}. "
            "Minor bumps are additive, so this is safe — but the data contains entries "
            "this build does not know about."
        )
    return None


def read_manifest(root: Path | None = None) -> list[str]:
    """Every path ``data/MANIFEST`` lists, in its declared order, as the relative
    strings written there — comments and blank lines stripped. Anything that reads
    only the files the manifest names (``pravapis build-artifact``, ``compute_data_hash``)
    starts here."""
    base = root or find_data_dir()
    manifest = base / "MANIFEST"
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DataVersionError(f"{manifest}: cannot read the data manifest: {exc}") from exc
    return [line for raw in lines if (line := raw.strip()) and not line.startswith("#")]


def _manifest_paths(root: Path) -> list[Path]:
    """Every path ``data/MANIFEST`` lists, resolved relative to ``root``, in order."""
    return [root / rel for rel in read_manifest(root)]


def compute_data_hash(root: Path | None = None) -> str:
    """Sha256 over every file ``data/MANIFEST`` lists, in its declared order.

    This is the one place "the data hash" is computed. Everything that reports or
    checks a data hash — GET /v1/version, the precompiled lexicon artifact's
    staleness check — calls this rather than hashing its own idea of what "the
    data" is; see ``data/MANIFEST`` for exactly what is hashed and why.
    """
    base = root or find_data_dir()
    digest = hashlib.sha256()
    for path in _manifest_paths(base):
        try:
            digest.update(path.read_bytes())
        except OSError as exc:
            raise DataVersionError(f"{path}: listed in MANIFEST but unreadable: {exc}") from exc
    return digest.hexdigest()
