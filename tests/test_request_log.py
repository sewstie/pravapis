from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from pravapis.api.main import create_app
from pravapis.config import Config


@pytest.fixture(scope="module")
def client(config: Config) -> Iterator[TestClient]:
    with TestClient(create_app(config)) as c:
        yield c


def test_request_is_logged_with_metadata_only(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    text = "Ішоў снег у Мінску."
    with caplog.at_level(logging.INFO, logger="pravapis.api.request"):
        r = client.post("/v1/convert", json={"text": text, "direction": "taraskievica"})
    assert r.status_code == 200

    [record] = [rec for rec in caplog.records if rec.name == "pravapis.api.request"]
    message = record.getMessage()

    assert "endpoint=/v1/convert" in message
    assert "status=200" in message
    assert "duration_ms=" in message
    assert "engine_version=" in message
    assert "data_version=" in message
    # The whole point: the request text itself is nowhere in the log record.
    assert text not in message
    assert "Ішоў" not in message
    assert "снег" not in message
