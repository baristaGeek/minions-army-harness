"""Tests for API health check endpoint."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi.testclient import TestClient

from minions_army.domain.models import SlackMessage, WebAPIMessage
from minions_army.infrastructure.api import routes
from minions_army.infrastructure.api.dependencies import (
    get_slack_webhook_service_factory,
    get_webapi_webhook_service_factory,
)
from minions_army.infrastructure.api.fastapi_app import app


@asynccontextmanager
async def _fake_session_context():
    yield object()


def test_health_check():
    """Test health check endpoint."""
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_api_root():
    """Test API root endpoint."""
    client = TestClient(app)
    response = client.get("/api/v1/")

    assert response.status_code == 200
    assert "message" in response.json()


def test_slack_webhook_accepts_simple_message(monkeypatch):
    """Test Slack webhook endpoint with dependency override."""

    class FakeSlackWebhookService:
        def __init__(self) -> None:
            self.ran_message: SlackMessage | None = None

        async def accept_message(self, payload: Any) -> SlackMessage:
            return SlackMessage(id=42, channel_id=payload.channel_id, text=payload.text)

        def run_container_for_message(self, message: SlackMessage) -> None:
            self.ran_message = message

    service = FakeSlackWebhookService()
    app.dependency_overrides[get_slack_webhook_service_factory] = lambda: (lambda _session: service)
    monkeypatch.setattr(routes, "_get_sessionmaker", lambda: (lambda: _fake_session_context()))
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/webhooks/slack/messages",
            json={"channel": "C123", "text": "deploy minion", "user": "U123"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "message_id": 42,
        "challenge": None,
    }
    assert service.ran_message is not None
    assert service.ran_message.id == 42


def test_webapi_webhook_accepts_message(monkeypatch):
    """Test Web API webhook endpoint with dependency override."""

    class FakeWebAPIWebhookService:
        def __init__(self) -> None:
            self.ran_message: WebAPIMessage | None = None
            self.accepted_message = False

        async def accept_message(self, payload: Any) -> WebAPIMessage:
            self.accepted_message = True
            return WebAPIMessage(
                id=44,
                session_id=payload.session_id,
                text=payload.text,
                user_id=payload.user_id,
            )

        def run_container_for_message(self, message: WebAPIMessage) -> None:
            self.ran_message = message

    service = FakeWebAPIWebhookService()
    app.dependency_overrides[get_webapi_webhook_service_factory] = lambda: (
        lambda _session: service
    )
    monkeypatch.setattr(routes, "_get_sessionmaker", lambda: (lambda: _fake_session_context()))
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/webhooks/webapi/messages",
            json={"sessionId": "session-123", "text": "deploy minion", "user": "U123"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "message_id": None,
        "session_id": "session-123",
    }
    assert service.accepted_message is False
    assert service.ran_message is not None
    assert service.ran_message.session_id == "session-123"
