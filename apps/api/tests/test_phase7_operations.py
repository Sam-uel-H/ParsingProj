from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def test_request_ids_are_returned_and_errors_are_standardized() -> None:
    client = TestClient(create_app())

    response = client.get("/does-not-exist", headers={"X-Request-ID": "phase7-test"})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "phase7-test"
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found"},
        "request_id": "phase7-test",
    }


def test_operational_logs_do_not_include_request_bodies() -> None:
    app = create_app()

    @app.post("/_test/logging")
    async def logging_probe(request: Request) -> dict[str, bool]:
        await request.body()
        return {"ok": True}

    secret_document_text = "CONFIDENTIAL-DOCUMENT-CONTENT-8421"
    with patch("app.core.middleware.logger.info") as log_info:
        response = TestClient(app).post("/_test/logging", content=secret_document_text)

    assert response.status_code == 200
    log_info.assert_called_once()
    logged = " ".join(str(value) for value in log_info.call_args.args)
    assert "request_completed method=%s path=%s status=%s duration_ms=%s" in logged
    assert "POST" in logged
    assert "/_test/logging" in logged
    assert secret_document_text not in logged


def test_unsupported_provider_configuration_fails_clearly() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="unsupported")  # type: ignore[arg-type]
