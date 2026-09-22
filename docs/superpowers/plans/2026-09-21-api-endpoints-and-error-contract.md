# API Endpoints & Error Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `GET /v1/rules/{id}` and `GET /v1/version` to the FastAPI service, raise the
single-request text cap to 100,000 characters with a real `413`, add a `≤500k`-char /
`≤100`-item cap to `/v1/convert/batch`, and make every error response on the `/v1/*`
routes a uniform `application/problem+json` (RFC 9457) body.

**Architecture:** A new `pravapis.api.problems` module defines the RFC 9457 shape and
three exception handlers (`HTTPException`, `RequestValidationError`, unhandled
`Exception`), registered once in `create_app`. Existing pydantic `Field(max_length=...)`
constraints on request text are removed — pydantic still catches type/enum errors
(→ 422 via the validation handler), but size limits are checked explicitly in the route
handlers so they can be reported as `413` instead. Two new read-only endpoints
(`/v1/rules/{rule_id}`, `/v1/version`) are added to the existing router; nothing about
`/v1/convert`, `/v1/transliterate`, `/v1/lexicon/{word}`, `/v1/stats`, `/health`, or the
serverless `/api/convert` function changes shape.

**Tech Stack:** FastAPI, Pydantic v2, Starlette exceptions, pytest + `fastapi.testclient.TestClient`.

**Spec:** The endpoint table and limits are drawn from the user's "3.2 Endpoints" note
(not a file in this repo) and reconciled against the existing normative contract at
`docs/API.md` and its implementation in `src/pravapis/api/{routes,schemas,main}.py`.
There is no written RFC 9457 `type`-URI scheme to follow, so this plan defines one
(`https://pravapis.dev/problems/<slug>`, a stable identifier — RFC 9457 §3 does not
require it to resolve) and documents it in `docs/API.md`.

## Global Constraints

- Target branch: `worktree-data-schemas` (this worktree). Do not touch `main` or the
  serverless `webapi.py` / `api/convert.py` / `deploy/vercel/README.md` / `public/index.html`
  — those keep their own 50,000-character limit and plain `{"error": ...}` body, which are
  out of scope.
- `GET /v1/lexicon/{word}` keeps its current response shape (`word`, `direction`,
  `lexicon`, `identity`, `rules`, `result`) — explicitly out of scope for this task.
- Single-request text cap (`/v1/convert`, `/v1/transliterate`) becomes **100,000**
  characters, enforced with `413`, not pydantic's `max_length` (which would give `422`).
- `/v1/convert/batch` caps at **100 items** and **500,000** total characters across all
  items, both enforced with `413`.
- Bad `direction` / `script` enum values keep returning **422** — pydantic already does
  this; only the response *body* changes shape (problem+json).
- Every error response under `/v1/*` uses `Content-Type: application/problem+json` and
  the fields `type`, `title`, `status`, `detail` (RFC 9457 §3), `type` being a stable URI
  under `https://pravapis.dev/problems/`.
- Run tests with `uv run pytest tests/test_api.py tests/test_api_errors.py -v`; run the
  full suite (`uv run pytest`) plus `uv run ruff check src tests` and
  `uv run mypy --strict src` before the final commit.

---

## Task 1: RFC 9457 problem+json infrastructure

**Files:**
- Create: `src/pravapis/api/problems.py`
- Modify: `src/pravapis/api/main.py`
- Test: `tests/test_api_errors.py`

**Interfaces:**
- Produces: `problems.ProblemError(status_code: int, type_: str, detail: str, **extra: Any)`
  — an `HTTPException` subclass a route can `raise` to get a specific problem type.
  `problems.TEXT_TOO_LONG`, `problems.BATCH_TOO_LARGE`, `problems.RULE_NOT_FOUND` — the
  `type` URI constants Task 2–4 raise with. `problems.register(app: FastAPI) -> None` —
  wires all three handlers onto a `FastAPI` instance.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_errors.py
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from pravapis.api.main import create_app
from pravapis.config import Config


@pytest.fixture(scope="module")
def client(config: Config) -> Iterator[TestClient]:
    with TestClient(create_app(config)) as c:
        yield c


def test_bad_direction_is_problem_json(client: TestClient) -> None:
    r = client.post("/v1/convert", json={"text": "x", "direction": "klingon"})
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["type"] == "https://pravapis.dev/problems/validation-error"
    assert body["status"] == 422
    assert body["title"]
    assert body["detail"]


def test_unknown_route_is_problem_json(client: TestClient) -> None:
    r = client.get("/v1/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["type"] == "https://pravapis.dev/problems/not-found"
    assert body["status"] == 404


def test_wrong_method_is_problem_json(client: TestClient) -> None:
    r = client.get("/v1/convert")
    assert r.status_code == 405
    body = r.json()
    assert body["type"] == "https://pravapis.dev/problems/method-not-allowed"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_errors.py -v`
Expected: all three FAIL — responses are still plain FastAPI/Starlette JSON
(`{"detail": ...}`), not problem+json.

- [ ] **Step 3: Write `src/pravapis/api/problems.py`**

```python
"""RFC 9457 (application/problem+json) error responses for the HTTP API.

Every error `/v1/*` returns — a bad enum value, an oversized body, an unknown rule id,
even an unmatched route — comes back in this one shape, so a client can branch on
`type` instead of parsing prose. `type` values are stable identifiers under a fixed
namespace; RFC 9457 §3 does not require them to resolve to a document (the RFC's own
degenerate case, "about:blank", does not).
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_TYPE_BASE: Final[str] = "https://pravapis.dev/problems/"
MEDIA_TYPE: Final[str] = "application/problem+json"

TEXT_TOO_LONG: Final[str] = f"{PROBLEM_TYPE_BASE}text-too-long"
BATCH_TOO_LARGE: Final[str] = f"{PROBLEM_TYPE_BASE}batch-too-large"
VALIDATION_ERROR: Final[str] = f"{PROBLEM_TYPE_BASE}validation-error"
RULE_NOT_FOUND: Final[str] = f"{PROBLEM_TYPE_BASE}rule-not-found"
NOT_FOUND: Final[str] = f"{PROBLEM_TYPE_BASE}not-found"
METHOD_NOT_ALLOWED: Final[str] = f"{PROBLEM_TYPE_BASE}method-not-allowed"
INTERNAL_ERROR: Final[str] = f"{PROBLEM_TYPE_BASE}internal-error"
GENERIC_ERROR: Final[str] = f"{PROBLEM_TYPE_BASE}error"

_TITLES: Final[dict[str, str]] = {
    TEXT_TOO_LONG: "Text too long",
    BATCH_TOO_LARGE: "Batch too large",
    VALIDATION_ERROR: "Invalid request",
    RULE_NOT_FOUND: "Rule not found",
    NOT_FOUND: "Not found",
    METHOD_NOT_ALLOWED: "Method not allowed",
    INTERNAL_ERROR: "Internal server error",
    GENERIC_ERROR: "Error",
}

#: Starlette's own status codes (unmatched route, wrong method) mapped to a type.
_STATUS_TYPE: Final[dict[int, str]] = {
    404: NOT_FOUND,
    405: METHOD_NOT_ALLOWED,
}


def _problem_response(status_code: int, type_: str, detail: str, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {
        "type": type_,
        "title": _TITLES.get(type_, "Error"),
        "status": status_code,
        "detail": detail,
        **extra,
    }
    return JSONResponse(status_code=status_code, content=body, media_type=MEDIA_TYPE)


class ProblemError(StarletteHTTPException):
    """Raise to produce a specific RFC 9457 problem instead of a generic one.

    A plain ``HTTPException(404, "no such thing")`` still becomes a valid (if generic)
    problem via :data:`_STATUS_TYPE` / :data:`GENERIC_ERROR`, but a call site that knows
    *which* problem it is — text too long, an unknown rule id — should raise this
    instead so the client gets a `type` it can branch on.
    """

    def __init__(self, status_code: int, type_: str, detail: str, **extra: Any):
        super().__init__(status_code=status_code, detail=detail)
        self.type = type_
        self.extra = extra


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc, ProblemError):
        return _problem_response(exc.status_code, exc.type, str(exc.detail), **exc.extra)
    type_ = _STATUS_TYPE.get(exc.status_code, GENERIC_ERROR)
    return _problem_response(exc.status_code, type_, str(exc.detail))


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = jsonable_encoder(exc.errors())
    messages = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
    return _problem_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        VALIDATION_ERROR,
        "; ".join(messages) or "request failed validation",
        errors=errors,
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return _problem_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, INTERNAL_ERROR, "an unexpected error occurred"
    )


def register(app: FastAPI) -> None:
    """Wire the three handlers onto ``app`` so every error is one shape."""
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
```

- [ ] **Step 4: Wire it into `create_app`**

In `src/pravapis/api/main.py`, add the import and one call:

```python
from pravapis.api import problems
```

and inside `create_app`, right after `app.include_router(router)`:

```python
    app.include_router(router)
    problems.register(app)
    return app
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_errors.py -v`
Expected: PASS. Also re-run `uv run pytest tests/test_api.py -v` — `test_convert_validation`
and `test_batch`'s over-limit assertions still expect `422` at this point (Task 2/3
change those to `413`), so they should still pass unchanged after this step.

- [ ] **Step 6: Commit**

```bash
git add src/pravapis/api/problems.py src/pravapis/api/main.py tests/test_api_errors.py
git commit -m "api: uniform RFC 9457 problem+json error responses"
```

---

## Task 2: 100k single-request cap, reported as 413

**Files:**
- Modify: `src/pravapis/api/schemas.py`
- Modify: `src/pravapis/api/routes.py`
- Test: `tests/test_api.py`, `tests/test_api_errors.py`

**Interfaces:**
- Consumes: `problems.ProblemError`, `problems.TEXT_TOO_LONG` (Task 1).
- Produces: `schemas.MAX_TEXT_LENGTH = 100_000` (raised from 50,000; no longer enforced
  via pydantic `Field(max_length=...)` — enforced in `routes.py` instead).
  `routes._check_text_length(text: str) -> None`, raising `ProblemError` at 413.

- [ ] **Step 1: Write the failing tests**

Update the existing `test_convert_validation` in `tests/test_api.py` — the length case
moves from 422 to 413, and the bound moves from 50,001 to 100,001:

```python
def test_convert_validation(client: TestClient) -> None:
    too_long = client.post(
        "/v1/convert", json={"text": "x" * 100_001, "direction": "taraskievica"}
    )
    assert too_long.status_code == 413
    assert too_long.json()["type"] == "https://pravapis.dev/problems/text-too-long"

    bad_direction = client.post("/v1/convert", json={"text": "x", "direction": "klingon"})
    assert bad_direction.status_code == 422

    extra_field = client.post(
        "/v1/convert", json={"text": "x", "direction": "taraskievica", "extra": 1}
    )
    assert extra_field.status_code == 422
```

Add a companion case for `/v1/transliterate` and one proving 100,000 exactly is still
accepted, in `tests/test_api_errors.py`:

```python
def test_text_at_the_cap_is_accepted(client: TestClient) -> None:
    r = client.post(
        "/v1/convert", json={"text": "а" * 100_000, "direction": "taraskievica"}
    )
    assert r.status_code == 200


def test_transliterate_text_too_long(client: TestClient) -> None:
    r = client.post("/v1/transliterate", json={"text": "а" * 100_001, "script": "lacinka"})
    assert r.status_code == 413
    assert r.json()["type"] == "https://pravapis.dev/problems/text-too-long"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api.py::test_convert_validation tests/test_api_errors.py -v`
Expected: FAIL — `text` is still capped at 50,000 by pydantic and the old test still
expects 422 for the length case.

- [ ] **Step 3: Remove the pydantic length cap, raise the limit**

In `src/pravapis/api/schemas.py`:

```python
MAX_TEXT_LENGTH = 100_000
MAX_BATCH = 100
MAX_BATCH_TOTAL_CHARS = 500_000
```

```python
class ConvertRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    direction: Orthography
    explain: bool = False
```

```python
class TransliterateRequest(BaseModel):
    """..."""  # docstring unchanged

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    script: Script = Script.LACINKA
    from_script: Script | None = None
    convert: bool = True
    direction: Orthography | None = None
```

(`Field(max_length=MAX_TEXT_LENGTH)` is removed from both — pydantic no longer rejects
an over-long `text`, so the route can report it as 413 instead of 422.)

- [ ] **Step 4: Enforce the cap explicitly in the routes**

In `src/pravapis/api/routes.py`, add the import and a small helper, then call it from
both `convert` and `transliterate`:

```python
from pravapis.api import problems
from pravapis.api.schemas import (
    ...,
    MAX_TEXT_LENGTH,
)
```

```python
def _check_text_length(text: str) -> None:
    if len(text) > MAX_TEXT_LENGTH:
        raise problems.ProblemError(
            413,
            problems.TEXT_TOO_LONG,
            f"text is {len(text)} characters; the limit is {MAX_TEXT_LENGTH}",
        )
```

```python
@router.post("/v1/convert", response_model=ConvertResponse)
def convert(req: ConvertRequest, converter: ConverterDep) -> ConvertResponse:
    _check_text_length(req.text)
    return _to_response(converter, req.text, req.direction, req.explain)


@router.post("/v1/transliterate", response_model=TransliterateResponse)
def transliterate(req: TransliterateRequest, converter: ConverterDep) -> TransliterateResponse:
    """Cyrillic ↔ Latin. See data/TRANSLIT.md for the schemes and their sources."""
    _check_text_length(req.text)
    if req.from_script is not None:
        ...  # rest of the function is unchanged
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api.py tests/test_api_errors.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/pravapis/api/schemas.py src/pravapis/api/routes.py tests/test_api.py tests/test_api_errors.py
git commit -m "api: raise the single-request text cap to 100k, report it as 413"
```

---

## Task 3: Batch limits — ≤100 items, ≤500k chars total, reported as 413

**Files:**
- Modify: `src/pravapis/api/schemas.py`
- Modify: `src/pravapis/api/routes.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `problems.ProblemError`, `problems.BATCH_TOO_LARGE`, `schemas.MAX_BATCH`,
  `schemas.MAX_BATCH_TOTAL_CHARS` (Task 2).
- Produces: `routes._check_batch(texts: list[str]) -> None`, raising `ProblemError` at 413.

- [ ] **Step 1: Write the failing tests**

Replace the batch over-limit assertions in `tests/test_api.py::test_batch`:

```python
def test_batch(client: TestClient) -> None:
    r = client.post(
        "/v1/convert/batch", json={"texts": ["снег", "свет"], "direction": "taraskievica"}
    )
    assert r.status_code == 200
    assert [x["text"] for x in r.json()["results"]] == ["сьнег", "сьвет"]

    too_many = client.post(
        "/v1/convert/batch", json={"texts": ["x"] * 101, "direction": "taraskievica"}
    )
    assert too_many.status_code == 413
    assert too_many.json()["type"] == "https://pravapis.dev/problems/batch-too-large"

    too_much = client.post(
        "/v1/convert/batch",
        json={"texts": ["x" * 250_000, "x" * 250_001], "direction": "taraskievica"},
    )
    assert too_much.status_code == 413
    assert too_much.json()["type"] == "https://pravapis.dev/problems/batch-too-large"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_api.py::test_batch -v`
Expected: FAIL — `texts` is still pydantic-capped at 100 items (giving 422, not 413) and
there is no total-character check at all.

- [ ] **Step 3: Drop the pydantic-level batch constraints**

In `src/pravapis/api/schemas.py`, remove the item-count `Field(max_length=...)` and the
per-item length validator — both move to an explicit check in the route:

```python
class BatchConvertRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    texts: list[str]
    direction: Orthography
    explain: bool = False
```

(Delete the `_each_text_bounded` `@field_validator` entirely — its job is now
`routes._check_batch`.)

- [ ] **Step 4: Enforce the batch limits in the route**

In `src/pravapis/api/routes.py`:

```python
from pravapis.api.schemas import (
    ...,
    MAX_BATCH,
    MAX_BATCH_TOTAL_CHARS,
)
```

```python
def _check_batch(texts: list[str]) -> None:
    if len(texts) > MAX_BATCH:
        raise problems.ProblemError(
            413,
            problems.BATCH_TOO_LARGE,
            f"batch has {len(texts)} items; the limit is {MAX_BATCH}",
        )
    total = sum(len(t) for t in texts)
    if total > MAX_BATCH_TOTAL_CHARS:
        raise problems.ProblemError(
            413,
            problems.BATCH_TOO_LARGE,
            f"batch is {total} characters total; the limit is {MAX_BATCH_TOTAL_CHARS}",
        )
```

```python
@router.post("/v1/convert/batch", response_model=BatchConvertResponse)
def convert_batch(req: BatchConvertRequest, converter: ConverterDep) -> BatchConvertResponse:
    _check_batch(req.texts)
    return BatchConvertResponse(
        results=[_to_response(converter, t, req.direction, req.explain) for t in req.texts]
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/pravapis/api/schemas.py src/pravapis/api/routes.py tests/test_api.py
git commit -m "api: cap /v1/convert/batch at 500k total characters, report overage as 413"
```

---

## Task 4: `GET /v1/rules/{rule_id}`

**Files:**
- Modify: `src/pravapis/api/schemas.py`
- Modify: `src/pravapis/api/routes.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `RuleEngine.get(rule_id: str) -> Rule | None` (`src/pravapis/rules/engine.py:345`).
  `Rule` fields used: `id`, `direction: Orthography`, `citation: str`,
  `description: str`, `pattern: regex.Pattern[str] | None`, `replacement: str`,
  `priority: int`, `repeat: bool`, `optional: bool`,
  `tests: tuple[RuleTest, ...]` where `RuleTest` has `input: str`, `expected: str`,
  `positive: bool` (`src/pravapis/rules/engine.py:64-87`). `Orthography.code` property
  gives `"n2t"` / `"t2n"` (`src/pravapis/types.py:35`).
  `problems.ProblemError`, `problems.RULE_NOT_FOUND` (Task 1).
- Produces: `schemas.RuleExample`, `schemas.RuleDetail` response models.

- [ ] **Step 1: Write the failing test**

```python
def test_rule_detail(client: TestClient) -> None:
    r = client.get("/v1/rules/palat.assim")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == "palat.assim"
    assert body["direction"] == "n2t"
    assert body["citation"]
    assert body["pattern"]
    assert any(e["input"] == "свет" and e["expected"] == "сьвет" for e in body["examples"])


def test_rule_detail_unknown_id(client: TestClient) -> None:
    r = client.get("/v1/rules/does.not.exist")
    assert r.status_code == 404
    assert r.json()["type"] == "https://pravapis.dev/problems/rule-not-found"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_api.py::test_rule_detail tests/test_api.py::test_rule_detail_unknown_id -v`
Expected: FAIL with 404 (no such route yet).

- [ ] **Step 3: Add the response models**

In `src/pravapis/api/schemas.py`:

```python
class RuleExample(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    input: str
    expected: str
    positive: bool


class RuleDetail(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    #: the direction this rule produces, as the wire code: ``n2t`` | ``t2n``
    direction: str
    citation: str
    description: str
    #: the regex source, or ``null`` for a rule backed by a Python function
    pattern: str | None
    replacement: str
    priority: int
    repeat: bool
    optional: bool
    examples: list[RuleExample]
```

- [ ] **Step 4: Add the route**

In `src/pravapis/api/routes.py`:

```python
from pravapis.api.schemas import (
    ...,
    RuleDetail,
    RuleExample,
)
```

```python
@router.get("/v1/rules/{rule_id}", response_model=RuleDetail)
def rule_detail(rule_id: str, converter: ConverterDep) -> RuleDetail:
    rule = converter.engine.get(rule_id)
    if rule is None:
        raise problems.ProblemError(
            404, problems.RULE_NOT_FOUND, f"no rule with id {rule_id!r}"
        )
    return RuleDetail(
        id=rule.id,
        direction=rule.direction.code,
        citation=rule.citation,
        description=rule.description,
        pattern=rule.pattern.pattern if rule.pattern is not None else None,
        replacement=rule.replacement,
        priority=rule.priority,
        repeat=rule.repeat,
        optional=rule.optional,
        examples=[
            RuleExample(input=t.input, expected=t.expected, positive=t.positive)
            for t in rule.tests
        ],
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS. (`palat.assim` is asserted elsewhere in the suite to exist and fire on
`свет` → `сьвет`, e.g. `tests/test_api.py::test_convert`, so it is safe to rely on here.)

- [ ] **Step 6: Commit**

```bash
git add src/pravapis/api/schemas.py src/pravapis/api/routes.py tests/test_api.py
git commit -m "api: add GET /v1/rules/{rule_id}"
```

---

## Task 5: `GET /v1/version`

**Files:**
- Create: `src/pravapis/dataversion.py` (add one function — file already exists, modify it)
- Modify: `src/pravapis/api/main.py`
- Modify: `src/pravapis/api/routes.py`
- Modify: `src/pravapis/api/schemas.py`
- Test: `tests/test_dataversion.py` (new), `tests/test_api.py`

**Interfaces:**
- Consumes: `Config.lexicon: Path`, `Config.rules: tuple[Path, ...]`
  (`src/pravapis/config.py:46,49`). `pravapis.__version__` (`src/pravapis/__init__.py:22`).
  `pravapis.dataversion.DATA_VERSION` (`src/pravapis/dataversion.py:23`).
- Produces: `dataversion.compute_data_hash(config: Config) -> str` — a hex SHA-256 over
  the lexicon file and rule files the converter was actually built from. Computed once
  in the app lifespan and stored as `app.state.data_hash`, read via a new
  `get_data_hash` dependency — not recomputed per request. `schemas.VersionResponse`.

- [ ] **Step 1: Write the failing test for `compute_data_hash`**

```python
# tests/test_dataversion.py
from __future__ import annotations

from pravapis.config import Config
from pravapis.dataversion import compute_data_hash


def test_data_hash_is_stable_and_hex(config: Config) -> None:
    h1 = compute_data_hash(config)
    h2 = compute_data_hash(config)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest
    int(h1, 16)  # does not raise


def test_data_hash_changes_with_rules(config: Config, tmp_path) -> None:
    import shutil

    other_rule = tmp_path / "extra.yaml"
    other_rule.write_text(
        "- id: test.extra\n  pattern: 'x'\n  replacement: 'y'\n  direction: taraskievica\n",
        encoding="utf-8",
    )
    changed = config.model_copy(update={"rules": (*config.rules, other_rule)})
    assert compute_data_hash(changed) != compute_data_hash(config)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_dataversion.py -v`
Expected: FAIL — `compute_data_hash` does not exist yet (`ImportError`).

- [ ] **Step 3: Implement `compute_data_hash`**

Add to `src/pravapis/dataversion.py` (after the existing `check_data_version`, keeping
the module's stdlib-only, dependency-free style):

```python
import hashlib


def _hash_file(h: "hashlib._Hash", path: Path) -> None:
    h.update(path.name.encode("utf-8") + b"\0")
    if path.is_file():
        h.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")


def compute_data_hash(config: "Config") -> str:
    """A hex SHA-256 over the exact data files this converter was built from.

    Covers the lexicon and rule files named on ``config`` — the pieces that actually
    determine what the converter outputs. Deliberately not the whole ``data/``
    directory (stress and morphology tables run to hundreds of KB and do not change
    what `/v1/convert` decides on most requests); a caller diagnosing "same engine
    version, different answer" wants this to move when the rules or lexicon move.
    """
    h = hashlib.sha256()
    _hash_file(h, config.lexicon)
    for rule_path in sorted(config.rules, key=lambda p: p.name):
        _hash_file(h, rule_path)
    return h.hexdigest()
```

Add the `Config` import (as a type-checking-only import to avoid a runtime circular
import, since `config.py` does not import `dataversion.py`, this is safe as a normal
import too — use whichever `ruff`/`mypy` prefers, matching the existing style in this
file):

```python
from pravapis.config import Config, find_data_dir
```

(Replace the existing `from pravapis.config import find_data_dir` line with this one.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_dataversion.py -v`
Expected: PASS.

- [ ] **Step 5: Compute the hash once in the lifespan, add the response model and route**

In `src/pravapis/api/schemas.py`:

```python
class VersionResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    engine_version: str
    data_version: str
    data_hash: str
```

In `src/pravapis/api/main.py`:

```python
from pravapis.dataversion import DATA_VERSION, compute_data_hash
```

```python
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved = _resolve_config(config)
        converter = Converter.from_config(resolved)
        app.state.converter = converter
        app.state.config = resolved
        app.state.data_hash = compute_data_hash(resolved)
        log.info(
            "pravapis %s ready: %s, %d rules, model=%s",
            __version__,
            converter.lexicon,
            len(converter.engine),
            converter.model_version,
        )
        yield
```

In `src/pravapis/api/routes.py`:

```python
from pravapis import __version__
from pravapis.dataversion import DATA_VERSION
from pravapis.api.schemas import (
    ...,
    VersionResponse,
)
```

```python
def get_data_hash(request: Request) -> str:
    data_hash: str = request.app.state.data_hash
    return data_hash


DataHashDep = Annotated[str, Depends(get_data_hash)]
```

```python
@router.get("/v1/version", response_model=VersionResponse)
def version(data_hash: DataHashDep) -> VersionResponse:
    return VersionResponse(
        engine_version=__version__, data_version=DATA_VERSION, data_hash=data_hash
    )
```

- [ ] **Step 6: Write the endpoint test**

```python
def test_version(client: TestClient) -> None:
    body = client.get("/v1/version").json()
    assert body["engine_version"]
    assert body["data_version"]
    assert len(body["data_hash"]) == 64
    int(body["data_hash"], 16)
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api.py tests/test_dataversion.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/pravapis/dataversion.py src/pravapis/api/main.py src/pravapis/api/routes.py src/pravapis/api/schemas.py tests/test_dataversion.py tests/test_api.py
git commit -m "api: add GET /v1/version with an engine, data, and data-hash triple"
```

---

## Task 6: Update `docs/API.md`, full verification

**Files:**
- Modify: `docs/API.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Update the endpoint table**

Replace the `## Endpoints` table:

```markdown
## Endpoints

| Method | Path | Returns |
|---|---|---|
| `POST` | `/v1/convert` | This contract. |
| `POST` | `/v1/convert/batch` | `{"results": [ <this contract>, … ]}`, up to 100 items, 500,000 characters total. |
| `POST` | `/api/convert` | This contract (serverless; the same bytes as `/v1/convert`). |
| `POST` | `/v1/transliterate` | `TransliterateResponse` — see above. |
| `GET` | `/v1/lexicon/{word}` | Lookup plus which rules would fire. |
| `GET` | `/v1/rules/{rule_id}` | The rule's text, citation, and its positive/negative test examples. |
| `GET` | `/v1/version` | `engine_version`, `data_version`, and a hex `data_hash` over the lexicon and rule files in use. |
| `GET` | `/v1/stats` | Lexicon size, rule count, model version. |
| `GET` | `/health` | Liveness. |
```

- [ ] **Step 2: Update the request cap and document the error contract**

Replace the last sentence of the `### Request` section:

```markdown
`direction` on the **request** is the target orthography — `"taraskievica"` or
`"narkamauka"` — not the `n2t`/`t2n` code. The response echoes the journey; the request
names the destination. `text` is capped at 100,000 characters on `/v1/convert` and
`/v1/transliterate`; `/v1/convert/batch` additionally caps at 100 items and 500,000
characters total across them. `/api/convert` (the serverless function) keeps its own,
separate 50,000-character cap — see `deploy/vercel/README.md`.

### Errors

Every `/v1/*` error response is `application/problem+json` (RFC 9457): `type`, `title`,
`status`, `detail`, always present. `type` is a stable identifier under
`https://pravapis.dev/problems/` — it is not required to resolve to a document.

| `type` suffix | `status` | When |
|---|---|---|
| `text-too-long` | 413 | `text` exceeds the endpoint's character cap. |
| `batch-too-large` | 413 | `/v1/convert/batch` exceeds 100 items or 500,000 characters total. |
| `validation-error` | 422 | A field fails validation — bad `direction`/`script`, wrong type, an unknown field. Carries an `errors` array with pydantic's own per-field detail. |
| `rule-not-found` | 404 | `/v1/rules/{rule_id}` names a rule that does not exist. |
| `not-found` | 404 | No route matches. |
| `method-not-allowed` | 405 | The route exists, the HTTP method does not. |
| `internal-error` | 500 | Unhandled server error. |
```

- [ ] **Step 3: Commit**

```bash
git add docs/API.md
git commit -m "docs: document /v1/rules, /v1/version, the 100k cap, and the problem+json error contract"
```

---

## Final verification

- [ ] Run the full suite: `uv run pytest`
- [ ] Run lint: `uv run ruff check src tests`
- [ ] Run types: `uv run mypy --strict src`
- [ ] Re-read `docs/API.md` end to end against the four implementation files
  (`schemas.py`, `routes.py`, `main.py`, `dataversion.py`) and confirm every table row
  and every documented field name matches the code exactly.
