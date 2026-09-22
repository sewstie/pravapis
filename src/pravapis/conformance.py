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
from pravapis.types import Method, Orthography, Script

#: Bumped when the *shape* of a case record changes. Distinct from the data version,
#: which says which data produced the cases.
CORPUS_SCHEMA_ID: Final[str] = "tag:pravapis,2026:schema:conformance:2"

#: Rules that run in the pipeline rather than the YAML engine. They change the output,
#: so the contract has to reach them too.
_PSEUDO_RULES: Final[tuple[str, ...]] = (
    "morph.particle",
    "morph.conj_i_j",
    "morph.initial_u_w",
    "lex.case_context",
    "loan.ment_suffix",
)

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
    #: for `offsets` cases only: the (start, end, from, to) of each change, with the
    #: span given in Unicode code points into `expected`. See docs/API.md.
    spans: tuple[tuple[int, int, str, str], ...] | None = None

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
        if self.spans is not None:
            record["spans"] = [list(span) for span in self.spans]
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


#: Inputs whose change offsets are pinned, read from data/eval/offset_cases.tsv.
OFFSET_CASES_FILE: Final[str] = "eval/offset_cases.tsv"


def _offset_cases(data_dir: Path, converter: Converter) -> Iterator[tuple[Case, str]]:
    """Cases that pin `start`/`end`, which no other kind of case can catch.

    Every other case asserts the converted *text*. A port that indexes strings in UTF-16
    code units instead of code points produces exactly the right text and the wrong
    offsets, and nothing in the corpus notices — until a caller slices the output with
    them. These cases carry the spans, so that port fails here instead of in production.
    """
    path = data_dir / OFFSET_CASES_FILE
    if not path.is_file():
        return
    index = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("	")
        if len(parts) < 2:
            continue
        text, code = parts[0], parts[1].strip()
        direction = Orthography.from_code(code)
        result = converter.convert(text, direction)
        yield (
            Case(
                id=f"offsets/{index:03d}",
                kind="offsets",
                direction=_DIRECTION_NAMES[direction],
                script=Script.CYRILLIC.value,
                rule=None,
                input=text,
                expected=result.text,
                spans=tuple((c.start, c.end, c.source, c.target) for c in result.changes),
            ),
            result.text,
        )
        index += 1


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
    produced += list(_offset_cases(data_dir, conv))
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


# --- the data boundary ----------------------------------------------------------------
#
# The conformance corpus is the contract, so anything that changes the output and is
# *not* exercised by a case is outside the contract: a port can get it wrong and still
# claim conformance. :func:`coverage` finds those. It is deliberately blunt — a rule with
# no inline tests, a lexicon table no case touches, a data file nothing reads — because
# the subtle version of this check is the one nobody runs.

#: Data files that legitimately produce no conformance case, and why. An exemption is a
#: sentence someone had to write, not a pattern: a file leaves this audit only when a
#: person says out loud why it is not part of the contract.
EXEMPT_DATA: Final[dict[str, str]] = {
    "eval/gold.tsv": (
        "the source of the `gold` cases — it produces the contract rather than being tested by it"
    ),
    "eval/tarask/gold_t2n.tsv": (
        "the source of the `heldout` cases — it produces the contract rather than "
        "being tested by it"
    ),
    "eval/roundtrip_regressions.tsv": (
        "the source of the `regression` cases — it produces the contract rather than "
        "being tested by it"
    ),
    "eval/ambiguous.tsv": (
        "classifier training data. The classifier is off unless a config names a "
        "model, so it changes no default output and is outside the contract"
    ),
    "eval/negative.tsv": (
        "words a Narkamaŭka and a Taraškievica writer spelled identically, which the "
        "converter must leave alone; asserted by tests/test_negative_set.py"
    ),
    "eval/known_fps.tsv": (
        "the ledger of accepted dev false positives; a ratchet input asserted by "
        "tests/test_ratchet.py, not a statement about any one conversion"
    ),
    "eval/baseline.json": (
        "the recorded metric floor the ratchet compares against; asserted by "
        "tests/test_ratchet.py and meaningless as a per-sentence case"
    ),
    "eval/recall_misses.tsv": (
        "a generated report of what recall missed, written for humans to read; "
        "nothing in the library reads it back"
    ),
    "eval/roundtrip_failures.tsv": (
        "a generated list of round-trip failures, written for humans; the ones that "
        "were fixed are pinned in roundtrip_regressions.tsv instead"
    ),
    "eval/roundtrip_corpus.txt": (
        "unlabelled Narkamaŭka sentences fed to the N -> T -> N property test; there "
        "is no expected output to turn into a case"
    ),
    "eval/tarask/corpus.tsv": (
        "genuine be-tarask sentences used to measure independent T -> N precision; "
        "input to the audit, never an assertion about the output"
    ),
    "eval/tarask/audit.tsv": (
        "human ok/wrong/unsure verdicts over the audit sample; it records what a "
        "reviewer decided, and no case can assert a human judgement"
    ),
    "corpora/parallel.tsv": (
        "the aligned wiki corpus recall and the ratchet are measured on; the contract "
        "does not convert it, and its sentences are not gold"
    ),
    "corpora/frequency_be.tsv": (
        "a word-frequency list, read only by the lexicon coverage report; it changes "
        "no conversion and asserts nothing"
    ),
    "corpora/frequency_tarask.tsv": (
        "a word-frequency list, read only when screening mined stem candidates for "
        "blast radius; it changes no conversion"
    ),
    "review/stem_candidates.tsv": (
        "the mined stem review queue; nothing applies it automatically and nothing "
        "in the converter reads it — it exists for a human to work through"
    ),
    "corpora/titles.checkpoint.jsonl": (
        "a resume checkpoint from a title-mining run that was committed by accident "
        '(4 MB, 227 lines of {"pairs": …}). Nothing reads it and it is not data. '
        "Exempted rather than deleted so the removal is a deliberate commit of its own."
    ),
    "names/w_names.tsv": (
        "retained as evidence about which names render English W, but NOTHING READS IT: "
        "Правілы 2008 §15 п.4 makes the T -> N reversal unconditional, so the exception "
        "list it was mined for no longer exists. See data/NORMS.md. Its natural use is "
        "the forward direction, which is an open question and not implemented."
    ),
}


#: Rules that legitimately produce no conformance case, and why. Same discipline as
#: EXEMPT_DATA: a rule leaves the audit only when someone writes the sentence.
EXEMPT_RULES: Final[dict[str, str]] = {
    "morph.conj_i_j": (
        "optional (Збор 2005 §13 says і *may* become й) and therefore off unless a "
        "caller asks for aggressive mode. The contract records default output, and a "
        "case file cannot express 'with aggressive on' without a new field on every "
        "record. Covered instead by its own unit tests; see data/NORMS.md, "
        "'Policy: optional forms'."
    ),
}


@dataclass(frozen=True, slots=True)
class CoverageGap:
    """One thing that changes the output and no conformance case pins down."""

    kind: str  # rule | lexicon | data
    name: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.name} — {self.detail}"


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """Per-item case counts for the three things the contract has to reach."""

    rules: dict[str, int]
    lexicon_tables: dict[str, int]
    data_files: dict[str, int]
    exempt: dict[str, str]

    @property
    def gaps(self) -> list[CoverageGap]:
        out: list[CoverageGap] = []
        for rule, count in sorted(self.rules.items()):
            if count == 0 and rule not in EXEMPT_RULES:
                out.append(
                    CoverageGap("rule", rule, "no conformance case; add inline tests to its YAML")
                )
        for table, count in sorted(self.lexicon_tables.items()):
            if count == 0:
                out.append(
                    CoverageGap(
                        "lexicon",
                        table,
                        "no case resolves through this table; add a gold row that uses it",
                    )
                )
        for path, count in sorted(self.data_files.items()):
            if count == 0 and path not in self.exempt:
                out.append(
                    CoverageGap(
                        "data",
                        path,
                        "no case depends on this file; give it a case, or exempt it with "
                        "a reason in pravapis.conformance.EXEMPT_DATA",
                    )
                )
        return out

    @property
    def ok(self) -> bool:
        return not self.gaps


#: Files that back a rule rather than carrying words of their own, and the rules that
#: cannot work without them. Coverage is attributed through the rule: a stress table with
#: no §3 case behind it is untested however many rows it has.
_BACKED_BY: Final[dict[str, tuple[str, ...]]] = {
    "stress/": ("morph.particle", "morph.initial_u_w"),
    # Longest prefix wins, so the function-word table is attributed to the rules that
    # read it rather than to whatever else lives under morphology/.
    "morphology/function_words.tsv": (
        "morph.particle",
        "morph.initial_u_w",
        "lex.case_context",
    ),
    "morphology/": ("loan.ment_suffix",),
    "lexicon/stems/": ("loan.e_to_eh", "loan.i_to_y", "loan.l_palatalization"),
    "lexicon/case/": ("lex.case_context",),
}


def _lexicon_tables(data_dir: Path) -> dict[str, set[str]]:
    """``relative path -> every lowercased word it can resolve, either side``."""
    from pravapis.lexicon.builder import read_tsv_pairs

    tables: dict[str, set[str]] = {}
    for path in sorted((data_dir / "lexicon").rglob("*.tsv")):
        if path.parent.name in {"stems", "case"}:
            # Neither is a plain source→target table: the stem inventory is an etymology
            # index and the case file keys on the preceding preposition. Both are covered
            # through the rules they back, in `_BACKED_BY`.
            continue
        words: set[str] = set()
        for source, target in read_tsv_pairs(path):
            words.add(source.lower())
            words.add(target.lower())
        tables[path.relative_to(data_dir).as_posix()] = words
    return tables


def _audited_data_files(data_dir: Path) -> list[str]:
    """Every shipped data file that could change what the converter outputs."""
    out: list[str] = []
    for path in sorted(data_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(data_dir).as_posix()
        if rel.startswith("reference/"):
            continue  # copyrighted sources, git-ignored, read by humans
        if path.parent.name == "schemas":
            continue  # schemas describe the data; they do not change the output
        if path.suffix in {".md", ""}:
            continue  # prose, and SOURCE/VERSION provenance notes
        out.append(rel)
    return out


def coverage(
    data_dir: Path, cases: list[Case], converter: Converter | None = None
) -> CoverageReport:
    """Which rules, lexicon tables and data files the conformance corpus actually pins.

    Attribution is by **replay**, not bookkeeping: every sentence case is converted again
    and the changes it makes are matched to the rule ids and lexicon tables that produced
    them. Counting what the cases *say* would only restate the generator, and the
    generator is the thing being audited.
    """
    conv = converter or Converter.from_config(Config.default(data_dir))

    rules: dict[str, int] = {}
    for path in sorted((data_dir / "rules").glob("*.yaml")):
        for rule in load_rules(path):
            rules[rule.id] = 0
    for pseudo in _PSEUDO_RULES:
        rules.setdefault(pseudo, 0)

    tables = _lexicon_tables(data_dir)
    table_hits: dict[str, int] = dict.fromkeys(tables, 0)
    data_files: dict[str, int] = dict.fromkeys(_audited_data_files(data_dir), 0)

    for case in cases:
        if case.rule is not None:
            rules[case.rule] = rules.get(case.rule, 0) + 1
        if case.kind not in {"gold", "heldout", "regression"}:
            continue
        direction = (
            Orthography.TARASKIEVICA
            if case.direction == _DIRECTION_NAMES[Orthography.TARASKIEVICA]
            else Orthography.NARKAMAUKA
        )
        for conversion in conv.convert(case.input, direction).conversions:
            if not conversion.changed:
                continue
            for fired in (conversion.rule_id or "").split("+"):
                if fired in rules:
                    rules[fired] += 1
            if conversion.method is Method.LEXICON:
                for rel, words in tables.items():
                    if conversion.source.lower() in words:
                        table_hits[rel] += 1

    for rel in data_files:
        if rel.startswith("rules/"):
            ids = {rule.id for rule in load_rules(data_dir / rel)}
            data_files[rel] = sum(rules.get(i, 0) for i in ids)
        elif rel in table_hits:
            data_files[rel] = table_hits[rel]
        elif rel.startswith("translit/"):
            stem = Path(rel).stem
            data_files[rel] = sum(1 for c in cases if c.kind == "translit" and c.script == stem)
        elif rel == OFFSET_CASES_FILE:
            data_files[rel] = sum(1 for c in cases if c.kind == "offsets")
        else:
            prefix = max((p for p in _BACKED_BY if rel.startswith(p)), key=len, default=None)
            if prefix is not None:
                data_files[rel] = sum(rules.get(i, 0) for i in _BACKED_BY[prefix])

    return CoverageReport(
        rules=rules,
        lexicon_tables=table_hits,
        data_files=data_files,
        exempt=dict(EXEMPT_DATA),
    )
