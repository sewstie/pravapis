"""CI guard: no log call in src/pravapis/api/ sits near a variable that could hold
request text or the unresolved list.

    python scripts/check_no_request_text_logging.py

Metadata-only logging (endpoint, direction, char count, duration, engine_version,
data_version, status — see pravapis.api.request_log) is fine and expected. What must
never appear near a log call is the request **text** itself, or the **unresolved**
list: a flagged "unresolved" token is still a fragment of user input, not metadata,
however short. Neither is a hash of the text a way around this — this check does not
special-case that, because the rule is "the identifier does not appear here", not
"the text is disguised well enough".

This is a proximity check over *code*, not raw text: it tokenizes each file (stdlib
``tokenize``, no new dependency) and only looks at NAME tokens, so a docstring or
comment that mentions "text" or "unresolved" in prose — this file's own module
docstring included — does not trip it. A real identifier named ``text`` or
``unresolved`` (a bare variable, or an attribute access like ``req.text`` /
``result.unresolved``, both tokenize as a NAME) within a few source lines of a log
call does.
"""

from __future__ import annotations

import sys
import tokenize
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "src" / "pravapis" / "api"

#: lines this many before/after a log call are scanned for a banned identifier
WINDOW: Final[int] = 5

#: identifiers that name a variable which could hold request text or the
#: unresolved-token list. Matched as whole NAME tokens, so this also catches
#: attribute access (``req.text``, ``result.unresolved``) without catching an
#: unrelated identifier that merely contains "text" as a substring.
BANNED: Final[frozenset[str]] = frozenset({"text", "unresolved"})


def _log_call_lines(tokens: list[tokenize.TokenInfo]) -> set[int]:
    """Line numbers where ``log.<name>(`` starts — tolerates whitespace/comments
    between tokens since it matches by token kind and value, not by raw text."""
    lines: set[int] = set()
    for i in range(len(tokens) - 3):
        a, b, c, d = tokens[i : i + 4]
        if (
            a.type == tokenize.NAME
            and a.string == "log"
            and b.type == tokenize.OP
            and b.string == "."
            and c.type == tokenize.NAME
            and d.type == tokenize.OP
            and d.string == "("
        ):
            lines.add(a.start[0])
    return lines


def _banned_identifier_lines(tokens: list[tokenize.TokenInfo]) -> dict[int, str]:
    """line number -> the banned identifier found there (first one, for the message)."""
    out: dict[int, str] = {}
    for tok in tokens:
        if tok.type == tokenize.NAME and tok.string in BANNED:
            out.setdefault(tok.start[0], tok.string)
    return out


def check_file(path: Path) -> list[str]:
    with path.open("rb") as fh:
        tokens = list(tokenize.tokenize(fh.readline))
    log_lines = _log_call_lines(tokens)
    banned_lines = _banned_identifier_lines(tokens)
    if not log_lines or not banned_lines:
        return []

    problems: list[str] = []
    for log_line in sorted(log_lines):
        for banned_line in sorted(banned_lines):
            if abs(banned_line - log_line) <= WINDOW:
                problems.append(
                    f"{path}:{log_line}: log call within {WINDOW} lines of "
                    f"{banned_lines[banned_line]!r} on line {banned_line}"
                )
    return problems


def main() -> int:
    if not API_DIR.is_dir():
        print(f"{API_DIR} does not exist; nothing to check")
        return 0

    problems: list[str] = []
    for path in sorted(API_DIR.rglob("*.py")):
        problems += check_file(path)

    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print(f"  {p}")
        print(
            "\nA log call in src/pravapis/api/ sits near a variable that could hold "
            "request text or the unresolved list. Metadata-only logging is fine "
            "(endpoint, direction, char count, duration, engine_version, data_version, "
            "status) — request text and unresolved tokens are not, ever. See "
            'docs/API.md, "Privacy".'
        )
        return 1
    print(f"ok — no log call in {API_DIR} sits near request text or the unresolved list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
