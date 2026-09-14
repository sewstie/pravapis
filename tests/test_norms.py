"""Every rule must be documented in data/NORMS.md with a source field."""

from __future__ import annotations

from pathlib import Path

import regex

from belnorm.pipeline import PARTICLE_RULE_ID
from belnorm.rules.engine import RuleEngine

NORMS = Path(__file__).resolve().parent.parent / "data" / "NORMS.md"


def _entries() -> dict[str, str]:
    """rule id → text of its section."""
    text = NORMS.read_text(encoding="utf-8")
    parts = regex.split(r"^### (\S+)\s*$", text, flags=regex.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


def test_every_rule_has_a_norms_entry(engine: RuleEngine) -> None:
    entries = _entries()
    ids = {r.id for r in engine.rules} | {PARTICLE_RULE_ID}
    missing = sorted(ids - set(entries))
    assert not missing, f"rules without a data/NORMS.md entry: {missing}"


def test_every_entry_has_a_source(engine: RuleEngine) -> None:
    for rule_id, body in _entries().items():
        m = regex.search(r"^- source: (.+)$", body, flags=regex.M)
        assert m and m.group(1).strip(), f"{rule_id}: no source field"


def test_no_stale_entries(engine: RuleEngine) -> None:
    ids = {r.id for r in engine.rules} | {PARTICLE_RULE_ID}
    stale = sorted(set(_entries()) - ids)
    assert not stale, f"NORMS.md documents rules that no longer exist: {stale}"
