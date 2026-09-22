"""The single precompiled artifact a cold-starting deployment loads at import.

``pravapis build-artifact`` reads **only** the files ``data/MANIFEST`` lists —
nothing else in ``data/`` is consulted, so a stray file left in e.g.
``data/lexicon/stems/`` cannot change the build (see ``tests/test_artifact.py``,
the negative test) — validates the ones that have a JSON Schema, builds the lexicon
trie and the compiled rule engine (etymology stems already resolved into it) plus the
handful of auxiliary tables the cascade needs, and pickles the lot into one file named
by the data hash that built it:

    pravapis-<compute_data_hash()>.bin

Naming the artifact by that hash, rather than by the data version or a build number,
is what makes "the artifact deployed" and "the hash GET /v1/version reports" the same
claim: if they ever disagree, one of them was built from a different ``data/`` than
the other, and the mismatch is visible in the filename instead of only in behaviour.

Loading it (:func:`load_artifact`) is a single ``pickle.load`` plus a ``Converter``
constructor call — no YAML parsing, no TSV parsing, no rule-dependency or stem-lookup
recomputation. That is the point: the parsing this module does happens once, at build
time, not on every cold start.

Not bundled, and so not covered by this artifact: the transliteration schemes
(Łacinka / the 2007 romanisation, loaded and cached lazily via
``pravapis.translit``) and the optional disambiguation classifier. A deployment that
only calls :func:`load_artifact` still parses YAML on its first transliteration
request. See README, "Precompiled artifact".
"""

from __future__ import annotations

import os
import pickle
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

from pravapis.config import Config, find_data_dir
from pravapis.dataversion import compute_data_hash, read_data_version, read_manifest
from pravapis.lexicon.case_forms import CaseForms
from pravapis.lexicon.store import Lexicon
from pravapis.morphology import MentSuffix
from pravapis.pipeline import Converter
from pravapis.rules.engine import RuleEngine
from pravapis.rules.function_words import FUNCTION_WORDS_FILE, FunctionWords
from pravapis.stress import StressTable

#: The shape of this pickle. Bump when a field is added or removed; a loader that
#: does not recognise the schema should refuse rather than guess.
ARTIFACT_SCHEMA: Final[str] = "tag:pravapis,2026:schema:artifact:1"


class ArtifactError(RuntimeError):
    """The artifact could not be built or loaded."""


def artifact_filename(data_hash: str) -> str:
    return f"pravapis-{data_hash}.bin"


@dataclass(frozen=True, slots=True)
class ConverterArtifact:
    """Everything :class:`~pravapis.pipeline.Converter` needs, pre-parsed and pre-compiled."""

    schema: str
    engine_version: str
    data_version: str
    data_hash: str
    lexicon: Lexicon
    engine: RuleEngine
    case_forms: CaseForms
    ment_suffix: MentSuffix
    function_words: FunctionWords
    stress: StressTable | None

    def converter(self) -> Converter:
        """A ready :class:`Converter` — no config, no disk access, no parsing."""
        return Converter(
            self.lexicon,
            self.engine,
            stress=self.stress,
            case_forms=self.case_forms,
            ment_suffix=self.ment_suffix,
            function_words=self.function_words,
        )


# --- validation -------------------------------------------------------------------
def validate_manifest_files(data_dir: Path | None = None) -> list[str]:
    """Schema-check every ``data/MANIFEST`` entry that has a JSON Schema.

    Plain source→target lexicon tables, the case-context table and the binary
    GrammarDB tables (``*.marisa``) have no schema — there is nothing to check them
    against, so they are silently skipped, the same way ``pravapis.dataspec.validate_data``
    treats them. ``jsonschema`` is imported lazily (via ``pravapis.dataspec``), same
    reason as everywhere else it is used: validating data is a build-time activity,
    not a runtime dependency of the library.
    """
    from pravapis.dataspec import (
        validate_function_words_file,
        validate_rules_file,
        validate_scheme_file,
        validate_stems_file,
    )
    from pravapis.lexicon.stems import SCHEMA_ID, read_declaration

    base = data_dir or find_data_dir()
    problems: list[str] = []
    for rel in read_manifest(base):
        path = base / rel
        if rel.startswith("rules/") and rel.endswith(".yaml"):
            problems += [str(p) for p in validate_rules_file(path, base)]
        elif rel.startswith("lexicon/stems/") and rel.endswith(".tsv"):
            if read_declaration(path).schema != SCHEMA_ID:
                problems.append(f"{path}: no '#!schema {SCHEMA_ID}' declaration")
                continue
            problems += [str(p) for p in validate_stems_file(path, base)]
        elif rel.startswith("translit/") and rel.endswith(".yaml"):
            problems += [str(p) for p in validate_scheme_file(path, base)]
        elif rel == FUNCTION_WORDS_FILE:
            problems += [str(p) for p in validate_function_words_file(path, base)]
        # else: no schema for this kind (plain lexicon tables, case table, *.marisa).
    return problems


# --- building -----------------------------------------------------------------------
def _clean_room_config(data_dir: Path, room: Path) -> Config:
    """Copy every ``data/MANIFEST`` file into ``room`` at its declared relative path,
    and nothing else, so whatever loads from ``room`` provably saw only those files —
    the property the negative test (an unlisted file changes nothing) depends on.
    """
    for rel in read_manifest(data_dir):
        src = data_dir / rel
        dst = room / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return Config(
        lexicon=room / "lexicon",
        rules=tuple(
            room / "rules" / name
            for name in ("palatalization.yaml", "loanwords.yaml", "morphology.yaml")
        ),
        case_forms=room / "lexicon" / "case",
        stems=room / "lexicon" / "stems",
        stress=room / "stress" if (room / "stress").is_dir() else None,
        morphology=room / "morphology" if (room / "morphology").is_dir() else None,
    )


#: Fixed so two builds of identical data are byte-identical. Several pickled fields
#: are frozensets several layers deep (Rule.exceptions, StemEntry.alternations,
#: FunctionWords.*), and frozenset iteration — hence pickle's byte output — depends on
#: str hashing, which Python randomises per process by default. Without pinning this,
#: `build_artifact` run twice on the same data, in two different processes, produces
#: two different (same-length, same-hash-*content*) files: exactly the silent
#: divergence `test_committed_artifact_is_not_stale` and the negative test both exist
#: to catch, so it cannot be left to chance.
_HASH_SEED: Final[str] = "0"
_DATA_ENV: Final[str] = "_PRAVAPIS_ARTIFACT_DATA_DIR"
_OUT_ENV: Final[str] = "_PRAVAPIS_ARTIFACT_OUT_DIR"


def build_artifact(data_dir: Path | None = None, out_dir: Path | None = None) -> Path:
    """Build ``pravapis-<data_hash>.bin`` from exactly the files ``data/MANIFEST`` lists.

    A schema problem is always fatal: an artifact built from data that fails its own
    schema is not a build with warnings, it is a wrong build.
    """
    base = data_dir or find_data_dir()
    out_root = out_dir or base
    if os.environ.get("PYTHONHASHSEED") != _HASH_SEED:
        return _build_in_reproducible_subprocess(base, out_root)
    return _build(base, out_root)


def _build_in_reproducible_subprocess(base: Path, out_root: Path) -> Path:
    env = {
        **os.environ,
        "PYTHONHASHSEED": _HASH_SEED,
        _DATA_ENV: str(base),
        _OUT_ENV: str(out_root),
    }
    result = subprocess.run(
        [sys.executable, "-c", "import pravapis.artifact as a; print(a._build_from_env())"],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ArtifactError(f"artifact build failed:\n{result.stderr}")
    return Path(result.stdout.strip())


def _build_from_env() -> Path:
    """Entry point for the reproducible-build subprocess; not for direct use."""
    return _build(Path(os.environ[_DATA_ENV]), Path(os.environ[_OUT_ENV]))


def _build(base: Path, out_root: Path) -> Path:
    problems = validate_manifest_files(base)
    if problems:
        raise ArtifactError(
            f"{len(problems)} manifest file(s) failed schema validation:\n  "
            + "\n  ".join(problems)
        )

    with TemporaryDirectory(prefix="pravapis-artifact-") as tmp:
        room = Path(tmp) / "data"
        config = _clean_room_config(base, room)
        converter = Converter.from_config(config)

    data_hash = compute_data_hash(base)
    artifact = ConverterArtifact(
        schema=ARTIFACT_SCHEMA,
        engine_version=_engine_version(),
        data_version=read_data_version(base),
        data_hash=data_hash,
        lexicon=converter.lexicon,
        engine=converter.engine,
        case_forms=converter.case_forms,
        ment_suffix=converter.ment_suffix,
        function_words=converter.function_words,
        stress=converter.stress,
    )
    out = out_root / artifact_filename(data_hash)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        pickle.dump(artifact, fh, protocol=pickle.HIGHEST_PROTOCOL)
    return out


def _engine_version() -> str:
    from pravapis import __version__

    return __version__


# --- loading --------------------------------------------------------------------------
def load_artifact(path: Path) -> ConverterArtifact:
    try:
        with path.open("rb") as fh:
            artifact = pickle.load(fh)
    except (pickle.UnpicklingError, EOFError, OSError) as exc:
        raise ArtifactError(f"{path}: not a pravapis artifact: {exc}") from exc
    if not isinstance(artifact, ConverterArtifact):
        raise ArtifactError(f"{path}: not a pravapis artifact")
    if artifact.schema != ARTIFACT_SCHEMA:
        raise ArtifactError(
            f"{path}: artifact schema {artifact.schema!r}, this build reads {ARTIFACT_SCHEMA!r}"
        )
    return artifact
