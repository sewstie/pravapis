from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from belnorm.api.main import create_app
from belnorm.config import Config


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
    assert body["stats"]["rule"] == 1
    assert body["stats"]["lexicon"] == 1
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


def test_stats(client: TestClient) -> None:
    body = client.get("/v1/stats").json()
    assert body["lexicon_size"] > 200
    assert body["rule_count"] >= 15
    assert body["model_version"] is None
    assert body["version"]
