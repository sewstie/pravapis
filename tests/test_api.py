from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from pravapis.api.main import create_app
from pravapis.config import Config


@pytest.fixture(scope="module")
def client(config: Config) -> Iterator[TestClient]:
    with TestClient(create_app(config)) as c:
        yield c


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_convert(client: TestClient) -> None:
    r = client.post(
        "/v1/convert", json={"text": "Ішоў снег у Мінску.", "direction": "taraskievica"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"] == "Ішоў сьнег у Менску."
    # `stats` left the frozen contract (docs/API.md); the same facts are in `changes`.
    stages = [c["stage"] for c in body["changes"]]
    assert stages.count("rule") == 1
    assert stages.count("lexicon") == 1
    assert body["direction"] == "n2t"
    assert body["engine_version"] and body["data_version"]
    assert body["unresolved"] == []
    assert body["explanations"] is None


def test_convert_with_explanations_and_reverse(client: TestClient) -> None:
    r = client.post(
        "/v1/convert",
        json={"text": "Сьнег у Менску", "direction": "narkamauka", "explain": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "Снег у Мінску"
    methods = {e["source"]: e["method"] for e in body["explanations"]}
    assert methods == {"Сьнег": "rule", "у": "unknown", "Менску": "lexicon"}
    assert body["explanations"][0]["rule_id"] == "palat.unassim"


def test_convert_validation(client: TestClient) -> None:
    assert (
        client.post(
            "/v1/convert", json={"text": "x" * 50_001, "direction": "taraskievica"}
        ).status_code
        == 422
    )
    assert client.post("/v1/convert", json={"text": "x", "direction": "klingon"}).status_code == 422
    assert (
        client.post(
            "/v1/convert", json={"text": "x", "direction": "taraskievica", "extra": 1}
        ).status_code
        == 422
    )


def test_batch(client: TestClient) -> None:
    r = client.post(
        "/v1/convert/batch", json={"texts": ["снег", "свет"], "direction": "taraskievica"}
    )
    assert r.status_code == 200
    assert [x["text"] for x in r.json()["results"]] == ["сьнег", "сьвет"]
    too_many = client.post(
        "/v1/convert/batch", json={"texts": ["x"] * 101, "direction": "taraskievica"}
    )
    assert too_many.status_code == 422
    too_long = client.post(
        "/v1/convert/batch", json={"texts": ["x" * 50_001], "direction": "taraskievica"}
    )
    assert too_long.status_code == 422


def test_lexicon_lookup(client: TestClient) -> None:
    r = client.get("/v1/lexicon/Мінск")
    assert r.status_code == 200
    body = r.json()
    assert body["lexicon"] == "Менск"
    assert body["result"]["method"] == "lexicon"
    assert body["identity"] is False

    r = client.get("/v1/lexicon/свіння", params={"direction": "taraskievica"})
    body = r.json()
    assert body["lexicon"] is None
    assert [t["rule_id"] for t in body["rules"]] == ["palat.geminate", "palat.assim"]
    assert body["result"]["target"] == "сьвіньня"


def test_version(client: TestClient) -> None:
    from pravapis.dataversion import compute_data_hash

    body = client.get("/v1/version").json()
    assert body["engine_version"]
    assert body["data_version"]
    assert body["data_hash"] == compute_data_hash()


def test_unresolved_query_param(client: TestClient) -> None:
    default = client.post("/v1/convert", json={"text": "без мяне", "direction": "taraskievica"})
    assert default.json()["unresolved"] == []

    flagged = client.post(
        "/v1/convert",
        json={"text": "без мяне", "direction": "taraskievica"},
        params={"unresolved": "true"},
    )
    assert flagged.json()["unresolved"] == ["мяне"]

    batch = client.post(
        "/v1/convert/batch",
        json={"texts": ["без мяне"], "direction": "taraskievica"},
        params={"unresolved": "true"},
    )
    assert batch.json()["results"][0]["unresolved"] == ["мяне"]


def test_etag_reflects_the_cache_key(client: TestClient) -> None:
    r1 = client.post("/v1/convert", json={"text": "снег", "direction": "taraskievica"})
    r2 = client.post("/v1/convert", json={"text": "снег", "direction": "taraskievica"})
    assert r1.headers["etag"] and r1.headers["etag"] == r2.headers["etag"]

    flagged = client.post(
        "/v1/convert",
        json={"text": "снег", "direction": "taraskievica"},
        params={"unresolved": "true"},
    )
    assert flagged.headers["etag"] != r1.headers["etag"]

    other_direction = client.post("/v1/convert", json={"text": "снег", "direction": "narkamauka"})
    assert other_direction.headers["etag"] != r1.headers["etag"]


def test_cache_does_not_change_the_answer(client: TestClient) -> None:
    """A cache hit must return exactly what a cache miss would have — same text in,
    same response out, whether or not this exact key was asked before."""
    first = client.post("/v1/convert", json={"text": "Германіі", "direction": "taraskievica"})
    second = client.post("/v1/convert", json={"text": "Германіі", "direction": "taraskievica"})
    assert first.json() == second.json()


def test_cors_allows_any_origin_without_credentials(client: TestClient) -> None:
    resp = client.options(
        "/v1/convert",
        headers={"Origin": "https://anything.example", "Access-Control-Request-Method": "POST"},
    )
    assert resp.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in resp.headers


def test_stats(client: TestClient) -> None:
    body = client.get("/v1/stats").json()
    assert body["lexicon_size"] > 200
    assert body["rule_count"] >= 15
    assert body["model_version"] is None
    assert body["version"]


def test_both_implementations_produce_the_same_bytes(client: TestClient) -> None:
    """The contract's actual claim: two implementations, one response.

    `/v1/convert` (FastAPI, Pydantic) and `/api/convert` (stdlib, serverless) reach the
    wire by completely different routes, and the whole point of freezing the shape is
    that a caller cannot tell them apart. Compared as serialized JSON rather than as
    dicts, because key order is part of the contract too.

    This is the test that catches the mismatches neither implementation's own tests can
    see — a Pydantic model that writes `"across": null` where the library omits the key
    looks perfectly correct until it is put next to the other one.
    """
    from pravapis.pipeline import Converter
    from pravapis.webapi import convert_payload

    converter = Converter.from_config(None)
    for text in (
        "🎉 Не быў без мяне ў Германіі",  # cross-word rules, astral offsets, unresolved
        "сталіца «Украіны»",  # a context that reached across a quotation mark
        "Снег і план",  # the documented example
        "лaпa",  # sanitizer-only: text moves, changes stay empty
        "",  # nothing at all
    ):
        serverless = convert_payload(converter, {"text": text, "direction": "taraskievica"})
        served = client.post("/v1/convert", json={"text": text, "direction": "taraskievica"}).json()
        served.pop("explanations")  # documented as outside the contract
        assert json.dumps(served, ensure_ascii=False) == json.dumps(
            serverless, ensure_ascii=False
        ), f"the two implementations disagree on {text!r}"
