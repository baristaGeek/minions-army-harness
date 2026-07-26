"""Tests for API routes."""

from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from minions_army.domain.exceptions import ValidationError
from minions_army.infrastructure.api import routes
from minions_army.infrastructure.api.dependencies import get_slack_webhook_service_factory
from minions_army.infrastructure.api.fastapi_app import app


@asynccontextmanager
async def _fake_session_context():
    yield object()


def test_slack_webhook_returns_challenge() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/webhooks/slack/messages",
        json={"challenge": "abc123", "channel": "C123", "text": "ignored"},
    )

    assert response.status_code == 202
    assert response.json()["challenge"] == "abc123"


def test_slack_webhook_returns_validation_error(monkeypatch) -> None:
    class FailingService:
        async def accept_message(self, payload):
            raise ValidationError("Slack message text cannot be empty")

        def run_container_for_message(self, message):
            raise AssertionError("should not be used")

    app.dependency_overrides[get_slack_webhook_service_factory] = lambda: (
        lambda _session: FailingService()
    )
    monkeypatch.setattr(routes, "_get_sessionmaker", lambda: (lambda: _fake_session_context()))
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/webhooks/slack/messages",
            json={"channel": "C123", "text": "   "},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]
