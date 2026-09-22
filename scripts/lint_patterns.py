"""CI guard: every regex pattern in data/rules/ is portable to a JS RegExp port.

    python scripts/lint_patterns.py

The rule engine (src/pravapis/rules/engine.py) compiles patterns with the third-party
``regex`` package, which happily accepts constructs JS's RegExp does not support even
with the ``u`` flag:

- ``\\w`` ``\\W`` ``\\b`` ``\\B`` are ASCII-only in JS without the (still patchy) ``v``
  flag — a Cyrillic letter never matches ``\\w`` there, so a rule built on it silently
  stops firing on Belarusian input. ``\\Z`` doesn't exist in JS at all (``$`` is the
  closest analogue, and it isn't the same thing across ``m``).
- Inline flags, global (``(?i)``) or scoped (``(?i:...)``), have no JS equivalent —
  ``new RegExp`` throws on a scoped group and silently ignores a global one depending on
  engine, neither of which is "the rule runs as written".
- Conditional groups (``(?(id)yes|no)``) don't exist in JS RegExp at all.

None of these raise at compile time in ``regex`` — the failure mode is a rule that
compiles fine and then never matches Cyrillic in a JS port. This lint catches it at
review time instead.

Rewrite an offender using the tokenizer's character-class building blocks
(``src/pravapis/tokenize.py``: ``BELARUSIAN_LETTERS``, ``APOSTROPHE_CLASS``, or the
``\\p{Cyrillic}``/``\\p{L}`` property classes ``regex`` and JS's ``u`` flag both
understand) rather than ``\\w``.

On top of the named-construct check, every pattern is compiled two more ways:

1. Python's *stdlib* ``re`` — deliberately not ``regex``. ``regex`` accepts a strictly
   larger grammar (e.g. variable-width lookbehind) than either stdlib ``re`` or JS
   RegExp, so it can't tell you a pattern is unportable. Stdlib ``re`` is a much closer
   proxy for what JS accepts, so failing there is a real portability signal — not just
   a name on the banned list above.
2. A Node subprocess, ``new RegExp(pattern, 'u')`` (scripts/lint_patterns_node.mjs) —
   the actual target runtime, so nothing about Node's own quirks has to be guessed at
   in Python.

A pattern failing either compile is unportable regardless of whether it also uses a
named construct above.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Final, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pravapis.rules.engine import load_rules

ROOT: Final[Path] = Path(__file__).resolve().parent.parent
RULES_DIR: Final[Path] = ROOT / "data" / "rules"
NODE_HELPER: Final[Path] = Path(__file__).resolve().parent / "lint_patterns_node.mjs"

#: Escape sequences that are ASCII-only (\w \W \b \B) or nonexistent (\Z) in JS RegExp.
_BANNED_ESCAPES: Final[frozenset[str]] = frozenset({"w", "W", "b", "B", "Z"})

#: Python re/regex flag letters that can appear in an inline-flags group, e.g. (?i) or
#: (?i:...). Deliberately excludes chars used by other (?...) constructs — =, !, <, :,
#: P, # — so a lookaround, named group, or plain non-capturing group never matches.
_FLAG_LETTERS: Final[str] = "aiLmsux"
_INLINE_FLAGS_RE: Final[re.Pattern[str]] = re.compile(
    rf"\(\?[{_FLAG_LETTERS}]+(?:-[{_FLAG_LETTERS}]+)?[:)]"
)


class PatternRef(NamedTuple):
    file: Path
    rule_id: str
    pattern: str


class Problem(NamedTuple):
    ref: PatternRef
    message: str


def collect_patterns(rules_dir: Path) -> list[PatternRef]:
    """Every regex pattern in every rule file, in file then rule order.

    Rules use ``regex.compile`` already — via ``load_rules`` this reuses the engine's
    own YAML-layout parsing (flat list or ``{direction, rules: [...]}``) instead of
    duplicating it, and ``.pattern`` on the compiled object is the untouched source
    string. Function-based rules (``function: module:callable``, no ``pattern``) have
    nothing to check here.
    """
    refs: list[PatternRef] = []
    for path in sorted(rules_dir.glob("*.yaml")):
        for rule in load_rules(path):
            if rule.pattern is not None:
                refs.append(PatternRef(path, rule.id, rule.pattern.pattern))
    return refs


def _find_banned_escapes(pattern: str) -> list[str]:
    """Escape tokens like ``\\w`` in the *unbanned* raw source, left to right.

    A hand-rolled scan rather than a regex over the pattern text: it has to walk
    backslash pairs one at a time regardless (``\\\\w`` is a literal backslash then
    ``w``, not the ``\\w`` class), and doing that by hand means the banned set and the
    "is this actually an escape" logic live in one place.
    """
    found: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        if pattern[i] == "\\" and i + 1 < n:
            escaped = pattern[i + 1]
            if escaped in _BANNED_ESCAPES:
                found.append(f"\\{escaped}")
            i += 2
        else:
            i += 1
    return found


def _find_inline_flags(pattern: str) -> list[str]:
    return [m.group(0) for m in _INLINE_FLAGS_RE.finditer(pattern)]


def _has_conditional_group(pattern: str) -> bool:
    return "(?(" in pattern


def check_banned_constructs(ref: PatternRef) -> list[Problem]:
    problems: list[Problem] = []
    for tok in _find_banned_escapes(ref.pattern):
        problems.append(
            Problem(ref, f"{tok!r} is ASCII-only or unsupported in JS RegExp (even with 'u')")
        )
    for tok in _find_inline_flags(ref.pattern):
        problems.append(Problem(ref, f"inline flag {tok!r} has no JS RegExp equivalent"))
    if _has_conditional_group(ref.pattern):
        problems.append(Problem(ref, "conditional group '(?(...)...)' does not exist in JS RegExp"))
    return problems


def check_stdlib_re(refs: list[PatternRef]) -> list[Problem]:
    problems: list[Problem] = []
    for ref in refs:
        try:
            re.compile(ref.pattern)
        except re.error as exc:
            problems.append(Problem(ref, f"stdlib re: {exc}"))
    return problems


def check_node_regexp(refs: list[PatternRef]) -> list[Problem]:
    if not refs:
        return []
    try:
        proc = subprocess.run(
            ["node", str(NODE_HELPER)],
            input=json.dumps([ref.pattern for ref in refs]),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except FileNotFoundError:
        print(
            "error: 'node' not found on PATH — install Node.js to run this lint "
            "(CI installs it via actions/setup-node)",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    if proc.returncode != 0:
        print(f"error: {NODE_HELPER} exited {proc.returncode}:\n{proc.stderr}", file=sys.stderr)
        raise SystemExit(2)
    results = json.loads(proc.stdout)
    problems: list[Problem] = []
    for ref, result in zip(refs, results, strict=True):
        if not result["ok"]:
            problems.append(Problem(ref, f"Node RegExp(..., 'u'): {result['error']}"))
    return problems


def main() -> int:
    if not RULES_DIR.is_dir():
        print(f"{RULES_DIR} does not exist; nothing to lint")
        return 0

    refs = collect_patterns(RULES_DIR)

    problems: list[Problem] = []
    for ref in refs:
        problems += check_banned_constructs(ref)
    problems += check_stdlib_re(refs)
    problems += check_node_regexp(refs)

    if problems:
        print(f"{len(problems)} problem(s) in {len(refs)} pattern(s):")
        for p in sorted(problems, key=lambda p: (str(p.ref.file), p.ref.rule_id)):
            print(f"  {p.ref.file.relative_to(ROOT)} :: {p.ref.rule_id} :: {p.message}")
            print(f"      pattern: {p.ref.pattern!r}")
        return 1

    print(f"ok — {len(refs)} pattern(s) in {RULES_DIR.relative_to(ROOT)} are JS-portable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
