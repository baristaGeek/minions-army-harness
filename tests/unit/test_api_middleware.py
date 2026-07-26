"""Tests for API middleware logging."""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from minions_army.infrastructure.api.fastapi_app import app


def test_logging_middleware_emits_request_lifecycle_events(caplog) -> None:
    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        response = client.get("/health")

    assert response.status_code == 200
    assert "event=http.request.started" in caplog.text
    assert "method=GET" in caplog.text
    assert "path=/health" in caplog.text
    assert "event=http.request.completed" in caplog.text
    assert "status_code=200" in caplog.text
