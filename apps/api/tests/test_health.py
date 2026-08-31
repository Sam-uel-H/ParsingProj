from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.routes import health as health_routes
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_health_is_live_without_database(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"] == {}


def test_ready_reports_database_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def ready() -> None:
        return None

    monkeypatch.setattr(health_routes, "database_is_ready", ready)
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok"}


def test_ready_hides_database_error_details(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable() -> None:
        raise RuntimeError("secret connection detail")

    monkeypatch.setattr(health_routes, "database_is_ready", unavailable)
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "unavailable"}
    assert "secret" not in response.text
