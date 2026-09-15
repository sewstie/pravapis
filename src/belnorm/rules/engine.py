"""Declarative rule engine.

Rules live in YAML (``data/rules/*.yaml``) so linguists can add them without
touching Python. A rule is either a regex substitution or a reference to a
pure ``str -> str`` function (``module:callable``); either way the engine
applies every rule for the requested direction in priority order and records
which ones changed the word.

Supported file layouts::

    # Skill-style: one direction per file
    version: "1.0"
    direction: narkamauka_to_taraskievica
    group: dental_assimilation
    rules:
      - id: palat.assim
        pattern: '(дз|[зсц])(?=(?:дз|[вмпблнсзц])[еёіюяь])'
        replacement: '\\1ь'
        repeat: true
        priority: 100
        exceptions: [супермен]
        tests:
          positive: [{input: свет, expected: сьвет}]
          negative: [{input: падсекчы, expected: падсекчы}]

    # Flat list, direction per rule
    - id: loan.eu
      pattern: '^еў'
      replacement: 'эў'
      direction: taraskievica
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any, Final

import regex
import yaml

from belnorm.types import Orthography, RuleTrace

_DIRECTION_ALIASES: Final[dict[str, Orthography]] = {
    "taraskievica": Orthography.TARASKIEVICA,
    "narkamauka": Orthography.NARKAMAUKA,
    "narkamauka_to_taraskievica": Orthography.TARASKIEVICA,
    "n2t": Orthography.TARASKIEVICA,
    "taraskievica_to_narkamauka": Orthography.NARKAMAUKA,
    "t2n": Orthography.NARKAMAUKA,
}

_MAX_REPEAT: Final[int] = 8


class RuleError(ValueError):
    """A rule file is malformed."""


@dataclass(frozen=True, slots=True)
class RuleTest:
    input: str
    expected: str
    positive: bool = True


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: regex.Pattern[str] | None
    replacement: str
    direction: Orthography  # the orthography this rule *produces*
    priority: int = 0
    requires: tuple[str, ...] = ()  # other rule ids that must fire first
    function: Callable[[str], str] | None = None
    repeat: bool = False  # apply until fixpoint (for chained softness)
    exceptions: frozenset[str] = field(default_factory=frozenset)
    description: str = ""
    tests: tuple[RuleTest, ...] = ()
    #: the codification permits both the input and the output form; applied only
    #: in aggressive mode (see data/NORMS.md, "Policy: optional forms")
    optional: bool = False

    def transform(self, word: str) -> str:
        if word in self.exceptions:
            return word
        if self.function is not None:
            return self.function(word)
        assert self.pattern is not None
        if not self.repeat:
            return self.pattern.sub(self.replacement, word)
        for _ in range(_MAX_REPEAT):
            new = self.pattern.sub(self.replacement, word)
            if new == word:
                break
            word = new
        return word


def parse_direction(value: str) -> Orthography:
    try:
        return _DIRECTION_ALIASES[value.strip().lower()]
    except KeyError as exc:
        raise RuleError(f"unknown direction {value!r}") from exc


def _resolve_function(ref: str) -> Callable[[str], str]:
    module_name, _, attr = ref.partition(":")
    if not module_name or not attr:
        raise RuleError(f"function reference must look like 'module:callable', got {ref!r}")
    module = importlib.import_module(module_name)
    fn = getattr(module, attr, None)
    if not callable(fn):
        raise RuleError(f"{ref!r} is not a callable")
    return fn  # type: ignore[no-any-return]


def _parse_tests(raw: Any) -> tuple[RuleTest, ...]:
    if not raw:
        return ()
    out: list[RuleTest] = []
    for positive, key in ((True, "positive"), (False, "negative")):
        for case in raw.get(key, []) or []:
            out.append(RuleTest(str(case["input"]), str(case["expected"]), positive))
    return tuple(out)


def _parse_rule(raw: dict[str, Any], default_direction: Orthography | None) -> Rule:
    try:
        rule_id = str(raw["id"])
    except KeyError as exc:
        raise RuleError("rule without an id") from exc
    direction_raw = raw.get("direction")
    if direction_raw is None:
        if default_direction is None:
            raise RuleError(f"rule {rule_id!r}: no direction (file has no default either)")
        direction = default_direction
    else:
        direction = parse_direction(str(direction_raw))

    pattern: regex.Pattern[str] | None = None
    function: Callable[[str], str] | None = None
    if "function" in raw:
        function = _resolve_function(str(raw["function"]))
    elif "pattern" in raw:
        try:
            pattern = regex.compile(str(raw["pattern"]))
        except regex.error as exc:
            raise RuleError(f"rule {rule_id!r}: bad pattern: {exc}") from exc
    else:
        raise RuleError(f"rule {rule_id!r}: needs 'pattern' or 'function'")

    requires_raw = raw.get("requires", ()) or ()
    exceptions_raw = raw.get("exceptions", ()) or ()
    return Rule(
        id=rule_id,
        pattern=pattern,
        replacement=str(raw.get("replacement", "")),
        direction=direction,
        priority=int(raw.get("priority", 0)),
        requires=tuple(str(r) for r in requires_raw),
        function=function,
        repeat=bool(raw.get("repeat", False)),
        exceptions=frozenset(str(e).lower() for e in exceptions_raw),
        description=str(raw.get("description", "")),
        tests=_parse_tests(raw.get("tests")),
        optional=bool(raw.get("optional", False)),
    )


def load_rules(path: Path) -> list[Rule]:
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if doc is None:
        return []
    if isinstance(doc, list):
        entries, default_direction = doc, None
    elif isinstance(doc, dict):
        entries = doc.get("rules", []) or []
        default_direction = (
            parse_direction(str(doc["direction"])) if doc.get("direction") is not None else None
        )
    else:
        raise RuleError(f"{path}: expected a list or a mapping at top level")
    rules: list[Rule] = []
    for raw in entries:
        if not isinstance(raw, dict):
            raise RuleError(f"{path}: every rule must be a mapping")
        rules.append(_parse_rule(raw, default_direction))
    return rules


def validate_rule_set(rules: Sequence[Rule]) -> list[str]:
    """Return human-readable problems: duplicate ids, dangling or cyclic ``requires``."""
    problems: list[str] = []
    seen: set[str] = set()
    for rule in rules:
        if rule.id in seen:
            problems.append(f"duplicate rule id {rule.id!r}")
        seen.add(rule.id)
    by_id = {r.id: r for r in rules}
    for rule in rules:
        for dep in rule.requires:
            if dep not in by_id:
                problems.append(f"rule {rule.id!r} requires unknown rule {dep!r}")
            elif by_id[dep].direction is not rule.direction:
                problems.append(f"rule {rule.id!r} requires {dep!r} from the other direction")
    sorter: TopologicalSorter[str] = TopologicalSorter(
        {r.id: [d for d in r.requires if d in by_id] for r in rules}
    )
    try:
        sorter.prepare()
    except CycleError as exc:
        problems.append(f"cycle in rule dependencies: {' -> '.join(exc.args[1])}")
    return problems


class RuleEngine:
    def __init__(self, rules: Iterable[Rule], *, include_optional: bool = False):
        self._rules: tuple[Rule, ...] = tuple(rules)
        self.include_optional = include_optional
        problems = validate_rule_set(self._rules)
        if problems:
            raise RuleError("; ".join(problems))
        self._by_direction: dict[Orthography, tuple[Rule, ...]] = {
            d: tuple(
                sorted(
                    (
                        r
                        for r in self._rules
                        if r.direction is d and (include_optional or not r.optional)
                    ),
                    key=lambda r: (-r.priority, r.id),
                )
            )
            for d in Orthography
        }
        self._repeat_rules: dict[Orthography, tuple[Rule, ...]] = {
            d: tuple(r for r in rs if r.repeat) for d, rs in self._by_direction.items()
        }

    @classmethod
    def from_yaml(cls, *paths: Path) -> RuleEngine:
        rules: list[Rule] = []
        for path in paths:
            rules.extend(load_rules(path))
        return cls(rules)

    def with_optional(self, include: bool = True) -> RuleEngine:
        """The same rule set, applying optional rules or not."""
        if include == self.include_optional:
            return self
        return RuleEngine(self._rules, include_optional=include)

    @property
    def rules(self) -> tuple[Rule, ...]:
        """Every loaded rule, optional ones included (applied or not)."""
        return self._rules

    def __len__(self) -> int:
        return len(self._rules)

    def rules_for(self, direction: Orthography) -> list[Rule]:
        """Rules applied in ``direction`` (optional ones only when included)."""
        return list(self._by_direction[direction])

    def get(self, rule_id: str) -> Rule | None:
        return next((r for r in self._rules if r.id == rule_id), None)

    def explain(self, word: str, direction: Orthography) -> list[RuleTrace]:
        """Apply every rule for ``direction`` and record the ones that changed the word.

        Rules run once in priority order; then the ``repeat`` rules are re-run
        together until none of them changes the word, so chained rewrites that
        feed each other (softness propagating across a geminate) reach a
        fixpoint regardless of their relative priority.
        """
        traces: list[RuleTrace] = []
        fired: set[str] = set()
        rules: Sequence[Rule] = self._by_direction[direction]
        for _ in range(_MAX_REPEAT):
            before = word
            for rule in rules:
                if any(dep not in fired for dep in rule.requires):
                    continue
                new = rule.transform(word)
                if new != word:
                    traces.append(RuleTrace(rule.id, word, new))
                    fired.add(rule.id)
                    word = new
            rules = self._repeat_rules[direction]
            if word == before or not rules:
                break
        return traces

    def apply(self, word: str, direction: Orthography) -> tuple[str, list[str]]:
        traces = self.explain(word, direction)
        ids = list(dict.fromkeys(t.rule_id for t in traces))  # unique, first-fired order
        return (traces[-1].after if traces else word), ids
