"""The cross-language contract: every case an implementation must reproduce.

``conformance/cases.jsonl`` is generated from the data — inline rule tests, inline
transliteration tests, the trusted gold subset, and the independent held-out
sentences — and flattened into one file of self-contained cases. A port is correct
iff it passes that file. Nothing in it is written by hand, so it cannot drift from
the data it describes; it is regenerated on every data change and committed.

Each case says at which **level** it applies, because the project's test material is
not all of one kind:

``rule``      Apply the single named rule, alone, to the lowercased input — with
              etymology resolved from the stem inventory if the rule is class-gated.
              These are the inline cases in ``data/rules/*.yaml``. They are unit
              contracts: ``свіння`` → ``сьвіння`` is what *palat.assim* does, not what
              the converter outputs (the pipeline goes on to write ``сьвіньня``).
``translit`` Apply the named scheme's table directly, with no orthography conversion
              — the ``--no-convert`` path. From the inline cases in
              ``data/translit/*.yaml``.
``gold``      Convert the whole sentence through the public API. From the trusted
              (``hand_written``) rows of ``data/eval/gold.tsv``.
``heldout``   The same, on genuine Taraškievica nobody derived from Narkamaŭka:
              the reviewed rows of ``data/eval/tarask/gold_t2n.tsv``.

**Only one direction is exported per gold file, and it is the one the file can
honestly support.** ``gold.tsv`` declares ``# origin: narkamauka``, so its
Narkamaŭka side is the original and only N → T is accuracy there; the reverse
would be asking the converter to undo its own transformation. ``gold_t2n.tsv`` is
genuine Taraškievica, so only T → N is exported from it. Round-trip behaviour is a
property test, not a conformance case.

**Cases the reference implementation does not pass go to ``known_failures.jsonl``,
not into the contract.** The gold set measures accuracy and the converter is at
99.0%, not 100%; putting the residue into ``cases.jsonl`` would mean no
implementation could ever pass it, and quietly dropping it would hide known gaps.
Both files are generated, both are committed, and the manifest counts both.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from pravapis.config import Config
from pravapis.dataspec import read_data_version
from pravapis.metrics import HAND_WRITTEN, UNSCORED, read_gold_rows
from pravapis.pipeline import Converter
from pravapis.rules.engine import Rule, RuleEngine, load_rules
from pravapis.translit import Transliterator
from pravapis.translit.engine import load_scheme
from pravapis.types import Orthography, Script

#: Bumped when the *shape* of a case record changes. Distinct from the data version,
#: which says which data produced the cases.
CORPUS_SCHEMA_ID: Final[str] = "tag:pravapis,2026:schema:conformance:1"

_DIRECTION_NAMES: Final[dict[Orthography, str]] = {
    Orthography.TARASKIEVICA: "narkamauka_to_taraskievica",
    Orthography.NARKAMAUKA: "taraskievica_to_narkamauka",
}


@dataclass(frozen=True, slots=True)
class Case:
    """One conformance case. The field order here is the field order on disk."""

    id: str
    kind: str  # rule | translit | gold | heldout
    direction: str | None
    script: str
    rule: str | None
    input: str
    expected: str

    def to_json(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "direction": self.direction,
            "script": self.script,
        }
        if self.rule is not None:
            record["rule"] = self.rule
        record["in"] = self.input
        record["out"] = self.expected
        return record


def _single_rule_engine(rule: Rule, stems: Any) -> RuleEngine:
    """An engine holding one rule, so a case exercises exactly that rule."""
    return RuleEngine([rule], include_optional=True, stems=stems)


def _rule_cases(rules_dir: Path, stems: Any) -> Iterator[tuple[Case, str]]:
    """Inline rule tests, with the output the reference implementation actually gives."""
    for path in sorted(rules_dir.glob("*.yaml")):
        for rule in load_rules(path):
            engine = _single_rule_engine(rule, stems)
            positives = negatives = 0
            for test in rule.tests:
                if test.positive:
                    index, positives = positives, positives + 1
                    label = "pos"
                else:
                    index, negatives = negatives, negatives + 1
                    label = "neg"
                actual, _ = engine.apply(test.input, rule.direction)
                yield (
                    Case(
                        id=f"rule/{rule.id}/{label}/{index}",
                        kind="rule",
                        direction=_DIRECTION_NAMES[rule.direction],
                        script=Script.CYRILLIC.value,
                        rule=rule.id,
                        input=test.input,
                        expected=test.expected,
                    ),
                    actual,
                )


def _translit_cases(translit_dir: Path) -> Iterator[tuple[Case, str]]:
    for path in sorted(translit_dir.glob("*.yaml")):
        scheme = load_scheme(path)
        transliterator = Transliterator(scheme)
        for index, test in enumerate(scheme.tests):
            actual = transliterator.transliterate(test.input).text
            yield (
                Case(
                    id=f"translit/{scheme.name}/{index:03d}",
                    kind="translit",
                    direction=None,
                    script=scheme.name,
                    rule=None,
                    input=test.input,
                    expected=test.expected,
                ),
                actual,
            )


def _gold_cases(
    path: Path, converter: Converter, *, kind: str, direction: Orthography, trusted: str | None
) -> Iterator[tuple[Case, str]]:
    """Sentence-level cases, in the one direction the file can honestly support."""
    index = 0
    for row in read_gold_rows(path):
        if row.provenance in UNSCORED:
            continue
        if trusted is not None and row.provenance != trusted:
            continue
        if direction is Orthography.TARASKIEVICA:
            source, expected = row.narkamauka, row.taraskievica
        else:
            source, expected = row.taraskievica, row.narkamauka
        actual = converter.convert(source, direction).text
        yield (
            Case(
                id=f"{kind}/{index:04d}",
                kind=kind,
                direction=_DIRECTION_NAMES[direction],
                script=Script.CYRILLIC.value,
                rule=None,
                input=source,
                expected=expected,
            ),
            actual,
        )
        index += 1


def _regression_cases(data_dir: Path, converter: Converter) -> Iterator[tuple[Case, str]]:
    """Round-trip regressions, pinned once fixed, in both directions.

    A regression is only pinned if it holds *both* ways: the bug was that one direction
    invented something the other could not undo. Exporting both directions is what makes
    the pin meaningful to a port.
    """
    from pravapis.metrics import read_regressions

    path = data_dir / "eval" / "roundtrip_regressions.tsv"
    if not path.is_file():
        return
    for index, (nark, tarask) in enumerate(read_regressions(path)):
        for direction, source, expected in (
            (Orthography.TARASKIEVICA, nark, tarask),
            (Orthography.NARKAMAUKA, tarask, nark),
        ):
            yield (
                Case(
                    id=f"regression/{index:03d}/{_DIRECTION_NAMES[direction].split('_')[0][:1]}2"
                    f"{_DIRECTION_NAMES[direction].split('_')[-1][:1]}",
                    kind="regression",
                    direction=_DIRECTION_NAMES[direction],
                    script=Script.CYRILLIC.value,
                    rule=None,
                    input=source,
                    expected=expected,
                ),
                converter.convert(source, direction).text,
            )


def build_corpus(
    data_dir: Path, converter: Converter | None = None
) -> tuple[list[Case], list[Case]]:
    """``(cases, known_failures)`` — the contract, and what the reference does not meet."""
    conv = converter or Converter.from_config(Config.default(data_dir))
    stems = conv.engine.stems  # the same etymology index the pipeline resolves against
    produced: list[tuple[Case, str]] = []
    produced += list(_rule_cases(data_dir / "rules", stems))
    produced += list(_translit_cases(data_dir / "translit"))
    produced += list(_regression_cases(data_dir, conv))
    produced += list(
        _gold_cases(
            data_dir / "eval" / "gold.tsv",
            conv,
            kind="gold",
            direction=Orthography.TARASKIEVICA,
            trusted=HAND_WRITTEN,
        )
    )
    t2n = data_dir / "eval" / "tarask" / "gold_t2n.tsv"
    if t2n.is_file():
        produced += list(
            _gold_cases(t2n, conv, kind="heldout", direction=Orthography.NARKAMAUKA, trusted=None)
        )
    cases = [case for case, actual in produced if actual == case.expected]
    failures = [case for case, actual in produced if actual != case.expected]
    return cases, failures


def write_jsonl(cases: list[Case], path: Path) -> str:
    """Write cases and return the sha256 of the bytes written.

    Newlines are written as ``\\n`` explicitly so the file is byte-identical on Windows
    and Linux — otherwise CI's regeneration check would fail on platform, not content.
    """
    payload = "".join(
        json.dumps(case.to_json(), ensure_ascii=False, separators=(",", ": ")) + "\n"
        for case in cases
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload.encode("utf-8"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_manifest(
    path: Path, *, data_dir: Path, cases: list[Case], failures: list[Case], digest: str
) -> None:
    by_kind: dict[str, int] = {}
    for case in cases:
        by_kind[case.kind] = by_kind.get(case.kind, 0) + 1
    manifest = {
        "schema": CORPUS_SCHEMA_ID,
        "data_version": read_data_version(data_dir),
        "cases": len(cases),
        "cases_by_kind": dict(sorted(by_kind.items())),
        "known_failures": len(failures),
        "sha256": digest,
        "note": (
            "Generated by `pravapis export-conformance`. A port claims conformance "
            "for a specific data_version, never in the abstract. Cases the reference "
            "implementation does not pass are in known_failures.jsonl, not here."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def export(data_dir: Path, out_dir: Path, converter: Converter | None = None) -> dict[str, Any]:
    """Regenerate the corpus. Returns the manifest contents."""
    cases, failures = build_corpus(data_dir, converter)
    digest = write_jsonl(cases, out_dir / "cases.jsonl")
    write_jsonl(failures, out_dir / "known_failures.jsonl")
    write_manifest(
        out_dir / "manifest.json",
        data_dir=data_dir,
        cases=cases,
        failures=failures,
        digest=digest,
    )
    manifest: dict[str, Any] = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    return manifest
