"""`docs/API.md` is normative, so it is checked like anything else that is normative.

A contract document that nobody verifies decays into a description of what the code used
to do, and the whole point of writing the four decisions down was that a port reads them
instead of reading the Python. These tests tie the document to the models: rename a
field in `schemas.py` and the document has to move with it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pravapis.api.schemas import Change, ChangeContext, ConvertResponse
from pravapis.conformance import CORPUS_SCHEMA_ID

DOC = Path(__file__).resolve().parent.parent / "docs" / "API.md"


@pytest.fixture(scope="module")
def doc() -> str:
    assert DOC.is_file(), f"{DOC} is missing — the contract has no written form"
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def example(doc: str) -> dict[str, object]:
    """The first JSON block in the document: the canonical response."""
    match = re.search(r"```json\n(.*?)\n```", doc, re.S)
    assert match, "the document must show the response as a JSON block"
    parsed: dict[str, object] = json.loads(match.group(1))
    return parsed


def test_the_documented_example_validates_against_the_model(
    example: dict[str, object],
) -> None:
    """The example is not prose. If it does not parse as a response, it is wrong."""
    ConvertResponse.model_validate(example)


def test_the_model_has_exactly_the_documented_fields(example: dict[str, object]) -> None:
    frozen = {name for name in ConvertResponse.model_fields if name != "explanations"}
    assert frozen == set(example), (
        "docs/API.md and ConvertResponse disagree about the response fields"
    )


def test_the_change_model_has_exactly_the_documented_fields(
    example: dict[str, object],
) -> None:
    changes = example["changes"]
    assert isinstance(changes, list) and changes, "the example must show a change"
    documented = set(changes[0])
    wire = {field.serialization_alias or name for name, field in Change.model_fields.items()}
    assert wire == documented, "docs/API.md and Change disagree about the change fields"


def test_the_library_shape_matches_the_documented_shape(example: dict[str, object]) -> None:
    """`to_dict()` is what the library returns and what the port copies; the FastAPI
    model is only one consumer of it. Both have to match the document."""
    from pravapis import convert

    produced = convert("Снег і план", {"to": "taraskievica"}).to_dict()
    assert set(produced) == set(example)
    assert set(produced["changes"][0]) == set(example["changes"][0])  # type: ignore[index]


def test_every_documented_field_order_is_the_real_one(example: dict[str, object]) -> None:
    """Field *order* is frozen too, and JSON preserves it, so a port that emits the
    keys in another order is producing a different file for a byte comparison."""
    from pravapis import convert

    produced = convert("Снег і план", {"to": "taraskievica"}).to_dict()
    assert list(produced) == list(example)
    assert list(produced["changes"][0]) == list(example["changes"][0])  # type: ignore[index]


def test_the_context_model_matches_the_documented_triggers(doc: str) -> None:
    for trigger in ("prev_word_vowel", "prev_word", "next_word"):
        assert trigger in doc, f"{trigger} is a real trigger and the document omits it"
    assert set(ChangeContext.model_fields) == {"trigger", "across", "rule"}


def test_the_four_decisions_are_all_written_down(doc: str) -> None:
    """The reason the file exists. Each is a parity bug if it is left implicit."""
    for heading in (
        "Offsets are into the output, in Unicode code points",
        "Sanitizer effects are not reported as changes",
        "`context` is populated for cross-word rules only",
        "`engine_version` and `data_version` are independent",
    ):
        assert heading in doc, f"docs/API.md no longer states: {heading}"


def test_the_document_shows_a_js_port_how_to_convert_offsets(doc: str) -> None:
    """The decision costs a JS port a bug unless the document says what to do instead."""
    assert "```js" in doc, "no JavaScript shown, so the conversion is left as an exercise"
    assert "codePointAt" in doc
    assert "UTF-16" in doc


def test_the_document_names_the_conformance_kind_that_pins_offsets(doc: str) -> None:
    assert "offsets" in doc
    assert "offset_cases.tsv" in doc


def test_the_document_names_the_conformance_kind_that_pins_unresolved(doc: str) -> None:
    assert "unresolved_cases.tsv" in doc


def test_the_corpus_schema_says_it_has_both_extra_fields(doc: str) -> None:
    assert CORPUS_SCHEMA_ID.endswith(":3"), (
        "the corpus schema gained `spans` (v2) and `unresolved` (v3); a version that "
        "does not say so lets a port read old rules and miss a field"
    )


def test_the_documented_versions_are_the_real_ones(example: dict[str, object]) -> None:
    """A stale version in the example is the cheapest possible way to mislead a reader
    about which two numbers they are looking at."""
    from pravapis import __version__
    from pravapis.dataversion import read_data_version

    assert example["engine_version"] == __version__
    assert example["data_version"] == read_data_version()


def test_out_of_contract_fields_are_named_as_such(doc: str) -> None:
    """`explanations` and `segments` exist. A port must be told it may skip them."""
    assert "What is *not* in the contract" in doc
    for field in ("explanations", "segments"):
        assert field in doc, f"{field} ships but the document does not place it"


def test_the_library_result_carries_no_out_of_contract_fields() -> None:
    """`to_dict()` is the port's reference, so it holds the frozen six and nothing else."""
    from pravapis import convert

    produced = convert("снег", {"to": "taraskievica"}).to_dict()
    assert "explanations" not in produced
    assert "segments" not in produced
    assert "stats" not in produced
