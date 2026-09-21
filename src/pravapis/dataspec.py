"""The data package as a specification: its schemas, its version, and the check.

Every data file pravapis reads — rule files, the stem inventory, transliteration
tables — is described by a JSON Schema in ``data/schemas/``. Those schemas are
*normative*. An implementation in another language reads them; it does not read this
module, and it certainly does not read :mod:`pravapis.rules.engine` and infer the
format from what the parser happens to accept.

This module is the Python side of that arrangement:

* it validates the shipped data against those schemas (``pravapis validate-data``),
* it re-runs the semantic checks that JSON Schema cannot express — cycle detection in
  rule dependencies, stem duplicates, alphabet coverage for a scheme,
* and it declares which **data version** this code implements, so a mismatch between
  code and data is a loud error rather than a subtly wrong conversion.

The schema check and the semantic checks are deliberately in one command: a file can
satisfy the schema and still be wrong (a rule that requires a rule from the other
direction), and a contributor should not have to know which gate catches what.

``jsonschema`` is imported lazily. Validating data is a development and CI activity,
so the core library stays installable without it; ``pip install pravapis[spec]``
adds it.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

import regex
import yaml

from pravapis.config import find_data_dir
from pravapis.lexicon.stems import (
    DECLARED_COLUMNS,
    SCHEMA_ID,
    StemEntry,
    StemError,
    read_declaration,
    read_stems,
    validate_stems,
)
from pravapis.rules.engine import RuleError, load_rules, validate_rule_set
from pravapis.translit.engine import SchemeError, load_scheme, validate_scheme

#: The data version this code implements. Compared against ``data/VERSION`` at load
#: time; see data/VERSIONING.md for what a major and a minor bump mean. Every
#: implementation — this one, a port — declares its own, and the conformance corpus
#: records the version it was generated from.
DATA_VERSION: Final[str] = "1.0.0"

#: The Cyrillic alphabet a transliteration scheme must be able to consume in full.
BELARUSIAN_ALPHABET: Final[str] = "абвгдеёжзійклмнопрстуўфхцчшыьэюя"

_SEMVER: Final[regex.Pattern[str]] = regex.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class DataVersionError(RuntimeError):
    """The data on disk is not a version this code can read."""


@dataclass(frozen=True, slots=True)
class Problem:
    """One thing wrong with a data file, in a form a human can act on."""

    file: Path
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.where}: {self.message}"


# --- versioning -----------------------------------------------------------------------
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
    understand, or vice versa, and converting anyway would produce answers that
    look fine and are not. A **minor** difference is not — minor bumps are additive
    (a stem added, an optional field), so older code reads newer data correctly, it
    simply does not exercise all of it. That case returns a note rather than raising.
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


# --- schemas --------------------------------------------------------------------------
def schema_dir(root: Path | None = None) -> Path:
    return (root or find_data_dir()) / "schemas"


@lru_cache(maxsize=8)
def _load_schema_cached(path: str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fh:
        loaded: dict[str, Any] = json.load(fh)
    return loaded


def load_schema(name: str, root: Path | None = None) -> dict[str, Any]:
    """Load ``data/schemas/<name>.schema.json``."""
    return _load_schema_cached(str(schema_dir(root) / f"{name}.schema.json"))


def _validator(schema: dict[str, Any]) -> Any:
    try:
        import jsonschema
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "validating data needs the jsonschema package: pip install 'pravapis[spec]'"
        ) from exc
    return jsonschema.Draft202012Validator(schema)


def _specific(error: Any) -> Any:
    """Descend into an ``anyOf``/``oneOf`` failure to the branch that nearly matched.

    Without this, a file that fails the top-level ``oneOf`` is reported as "the whole
    document is not valid" followed by the whole document — true, useless, and exactly
    the kind of error message that makes people stop running the validator.
    """
    import jsonschema.exceptions

    while error.context:
        best = jsonschema.exceptions.best_match(error.context)
        if best is None:
            break
        error = best
    return error


def _schema_problems(file: Path, schema: dict[str, Any], instance: Any, where: str) -> list[Problem]:
    out: list[Problem] = []
    errors = [_specific(e) for e in _validator(schema).iter_errors(instance)]
    for error in sorted(errors, key=lambda e: [str(p) for p in e.absolute_path]):
        path = list(error.absolute_path)
        # Name the rule or mapping rather than its index: "rules/3" tells nobody anything.
        if len(path) >= 2 and path[0] == "rules" and isinstance(instance, dict):
            rules = instance.get("rules") or []
            if isinstance(path[1], int) and path[1] < len(rules):
                named = rules[path[1]].get("id", path[1])
                path = [f"rule {named}", *path[2:]]
        location = "/".join(str(p) for p in path) or where
        out.append(Problem(file, location, error.message))
    return out


# --- rule files -----------------------------------------------------------------------
def validate_rules_file(path: Path, root: Path | None = None) -> list[Problem]:
    """Schema, then the semantics the schema cannot state."""
    try:
        with path.open(encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        return [Problem(path, "<file>", f"not valid YAML: {exc}")]
    problems = _schema_problems(path, load_schema("rules", root), doc, "<document>")
    if problems:
        return problems  # a file that fails the schema will fail the parser too
    try:
        rules = load_rules(path)
    except RuleError as exc:
        return [Problem(path, "<file>", str(exc))]
    problems += [Problem(path, "<rule set>", m) for m in validate_rule_set(rules)]
    seen: dict[str, str] = {}
    for rule in rules:
        if rule.id in seen:
            problems.append(Problem(path, rule.id, "duplicate rule id"))
        seen[rule.id] = rule.citation
        # A rule's own tests must actually hold, or the inline cases are decoration —
        # and they are exported into the conformance corpus, where a port would inherit
        # the lie.
        for test in rule.tests:
            got = rule.transform(test.input, None) if rule.requires_class is None else None
            if got is None:
                continue  # etymology-gated: only the pipeline can supply the stem match
            if test.positive and got != test.expected:
                problems.append(
                    Problem(path, rule.id, f"positive test {test.input!r} gave {got!r}, "
                            f"expected {test.expected!r}")
                )
            elif not test.positive and got != test.expected:
                problems.append(
                    Problem(path, rule.id, f"negative test {test.input!r} was changed to {got!r}")
                )
    return problems


# --- stem inventory -------------------------------------------------------------------
def _cell_patterns(schema: dict[str, Any]) -> list[tuple[str, regex.Pattern[str], bool]]:
    columns = schema["x-tsv"]["columns"]
    return [
        (c["name"], regex.compile(c["pattern"]), bool(c["required"]))
        for c in sorted(columns, key=lambda c: int(c["index"]))
    ]


def _entry_as_row(entry: StemEntry) -> dict[str, Any]:
    return {
        "stem": entry.stem,
        "anchored": entry.anchored,
        "class": entry.cls.value,
        "alternations": sorted(entry.alternations),
        "forward_only": sorted(entry.forward_only),
        "source": entry.source,
        "provenance": entry.provenance.value,
        "target": entry.target,
    }


def _data_lines(path: Path) -> Iterator[tuple[int, str]]:
    with path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            line = raw.rstrip("\r\n")
            if line.strip() and not line.lstrip().startswith("#"):
                yield line_no, line


def validate_stems_file(path: Path, root: Path | None = None) -> list[Problem]:
    """The declaration, then the raw cells, then the parsed rows."""
    schema = load_schema("stems", root)
    problems: list[Problem] = []

    declaration = read_declaration(path)
    if declaration.schema is None:
        problems.append(
            Problem(path, "<declaration>", f"no '#!schema' directive; expected {SCHEMA_ID}")
        )
    elif declaration.schema != SCHEMA_ID:
        problems.append(
            Problem(path, "<declaration>", f"declares schema {declaration.schema!r}, "
                    f"but this build implements {SCHEMA_ID!r}")
        )
    if not declaration.columns:
        problems.append(Problem(path, "<declaration>", "no '#!columns' directive"))
    elif declaration.columns != DECLARED_COLUMNS[: len(declaration.columns)]:
        problems.append(
            Problem(path, "<declaration>", f"declares columns {declaration.columns}, "
                    f"but the schema orders them {DECLARED_COLUMNS}")
        )

    patterns = _cell_patterns(schema)
    required = sum(1 for _, _, req in patterns if req)
    for line_no, line in _data_lines(path):
        cells = [c.strip() for c in line.split("\t")]
        if len(cells) < required:
            problems.append(
                Problem(path, f"line {line_no}", f"{len(cells)} columns, needs at least {required}")
            )
            continue
        if len(cells) > len(patterns):
            problems.append(
                Problem(path, f"line {line_no}", f"{len(cells)} columns, schema declares "
                        f"{len(patterns)}")
            )
            continue
        for cell, (name, pattern, _) in zip(cells, patterns, strict=False):
            if not pattern.match(cell):
                problems.append(
                    Problem(path, f"line {line_no}", f"column {name}: {cell!r} does not match "
                            f"{pattern.pattern}")
                )

    try:
        entries = list(read_stems(path))
    except StemError as exc:
        problems.append(Problem(path, "<file>", str(exc)))
        return problems
    row_schema = {**schema["$defs"]["row"], "$defs": schema["$defs"]}
    for entry in entries:
        problems += _schema_problems(path, row_schema, _entry_as_row(entry), entry.stem)
    problems += [Problem(path, "<inventory>", m) for m in validate_stems(entries)]
    return problems


# --- transliteration schemes ----------------------------------------------------------
def validate_scheme_file(path: Path, root: Path | None = None) -> list[Problem]:
    try:
        with path.open(encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        return [Problem(path, "<file>", f"not valid YAML: {exc}")]
    problems = _schema_problems(path, load_schema("translit", root), doc, "<document>")
    if problems:
        return problems
    try:
        scheme = load_scheme(path)
    except SchemeError as exc:
        return [Problem(path, "<file>", str(exc))]

    seen: set[tuple[str, tuple[str, ...]]] = set()
    for mapping in scheme.mappings:
        key = (mapping.source, mapping.when)
        if key in seen:
            problems.append(
                Problem(path, mapping.source, f"a second mapping for {mapping.source!r} under "
                        f"{'|'.join(mapping.when)} can never be reached")
            )
        seen.add(key)

    # Coverage: a Cyrillic → Latin scheme must be able to consume the whole alphabet.
    # A reverse scheme reads Latin, so the Cyrillic alphabet is not its input.
    if "reverse" not in path.stem:
        missing = validate_scheme(scheme, BELARUSIAN_ALPHABET)
        if missing:
            problems.append(
                Problem(path, "<coverage>", f"no mapping consumes {', '.join(missing)}")
            )
    # The scheme's own test cases are behaviour, not shape: they are exported into the
    # conformance corpus and checked there, against the same transducer a port must match.
    return problems


# --- the conformance corpus -----------------------------------------------------------
def validate_corpus_file(path: Path, root: Path | None = None) -> list[Problem]:
    """Every line of a ``*.jsonl`` corpus against the conformance schema.

    The corpus is generated, so this is not guarding against a typing human — it is
    guarding against the generator and the published record shape drifting apart,
    which is exactly the drift a port would be caught by.
    """
    schema = load_schema("conformance", root)
    problems: list[Problem] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                problems.append(Problem(path, f"line {line_no}", f"not valid JSON: {exc}"))
                continue
            problems += _schema_problems(path, schema, record, f"line {line_no}")
    return problems


# --- the whole data package -----------------------------------------------------------
def validate_data(root: Path | None = None) -> list[Problem]:
    """Validate every data file pravapis ships. An empty list means the data is well-formed."""
    base = root or find_data_dir()
    problems: list[Problem] = []
    try:
        note = check_data_version(base)
    except DataVersionError as exc:
        problems.append(Problem(base / "VERSION", "<version>", str(exc)))
    else:
        if note:
            problems.append(Problem(base / "VERSION", "<version>", note))

    for path in sorted((base / "rules").glob("*.yaml")):
        problems += validate_rules_file(path, base)
    for path in sorted((base / "lexicon" / "stems").glob("*.tsv")):
        problems += validate_stems_file(path, base)
    for path in sorted((base / "translit").glob("*.yaml")):
        problems += validate_scheme_file(path, base)

    # The corpus lives outside the data directory — it is generated *from* the data —
    # but it is part of the same contract, so one command checks both.
    corpus = base.parent / "conformance"
    for name in ("cases.jsonl", "known_failures.jsonl"):
        if (corpus / name).is_file():
            problems += validate_corpus_file(corpus / name, base)
    return problems


def format_problems(problems: Iterable[Problem]) -> str:
    return "\n".join(str(p) for p in problems)
