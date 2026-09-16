"""Every rule must be documented in data/NORMS.md with a source field."""

from __future__ import annotations

from pathlib import Path

import regex

from pravapis.lexicon.case_forms import CASE_RULE_ID
from pravapis.pipeline import PARTICLE_RULE_ID
from pravapis.rules.engine import RuleEngine
from pravapis.rules.morphology import CONJ_RULE_ID
from pravapis.types import Orthography

PIPELINE_RULE_IDS = {PARTICLE_RULE_ID, CONJ_RULE_ID, CASE_RULE_ID}

NORMS = Path(__file__).resolve().parent.parent / "data" / "NORMS.md"


def _entries() -> dict[str, str]:
    """rule id → text of its section."""
    text = NORMS.read_text(encoding="utf-8")
    parts = regex.split(r"^### (\S+)\s*$", text, flags=regex.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


def test_every_rule_has_a_norms_entry(engine: RuleEngine) -> None:
    entries = _entries()
    ids = {r.id for r in engine.rules} | PIPELINE_RULE_IDS
    missing = sorted(ids - set(entries))
    assert not missing, f"rules without a data/NORMS.md entry: {missing}"


def test_every_entry_has_a_source(engine: RuleEngine) -> None:
    for rule_id, body in _entries().items():
        m = regex.search(r"^- source: (.+)$", body, flags=regex.M)
        assert m and m.group(1).strip(), f"{rule_id}: no source field"


def test_no_stale_entries(engine: RuleEngine) -> None:
    ids = {r.id for r in engine.rules} | PIPELINE_RULE_IDS
    stale = sorted(set(_entries()) - ids)
    assert not stale, f"NORMS.md documents rules that no longer exist: {stale}"


def test_optional_rules_are_documented_as_optional(engine: RuleEngine) -> None:
    """Policy: every optional rule's NORMS entry says so, and it is off by default."""
    entries = _entries()
    optional = {r.id for r in engine.rules if r.optional} | {CONJ_RULE_ID}
    assert optional, "expected at least one optional rule"
    for rule_id in optional:
        assert "**optional**" in entries[rule_id], rule_id
    applied = {r.id for d in Orthography for r in engine.rules_for(d)}
    assert not (optional & applied), "optional rules must be off in the default engine"
